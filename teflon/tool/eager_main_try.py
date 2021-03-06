# Copyright (c) 2020 Mitsubishi Electric Research Laboratories (MERL). All rights reserved.

# The software, documentation and/or data in this file is provided on an "as is" basis, and MERL has no obligations to provide maintenance, support, updates, enhancements or modifications. MERL specifically disclaims any warranties, including, but not limited to, the implied warranties of merchantability and fitness for any particular purpose. In no event shall MERL be liable to any party for direct, indirect, special, incidental, or consequential damages, including lost profits, arising out of the use of this software and its documentation, even if MERL has been advised of the possibility of such damages.

# As more fully described in the license agreement that was required in order to download this software, documentation and/or data, permission to use, copy and modify this software without fee is granted, but only for educational, research and non-commercial purposes.


import argparse
import logging
import os
import shutil
import sys
import time

import gin
import gym
import numpy as np
import tensorflow as tf

import teflon.util.gin_utils as gin_utils
from teflon.ofe.dummy_extractor import DummyFeatureExtractor
from teflon.ofe.munk_extractor import MunkNet
from teflon.ofe.network import OFENet
from teflon.policy import DDPG
from teflon.policy import SAC as SAC
from teflon.policy import TD3
from teflon.util import misc
from teflon.util import replay
from teflon.util.misc import get_target_dim, make_ofe_name

# misc.set_gpu_device_growth()


def evaluate_policy(env, policy, eval_episodes=10):
    avg_reward = 0.
    episode_length = []

    for _ in range(eval_episodes):
        state = env.reset()
        cur_length = 0

        done = False
        while not done:
            action = policy.select_action(np.array(state))
            state, reward, done, _ = env.step(action)
            avg_reward += reward
            cur_length += 1

        episode_length.append(cur_length)

    avg_reward /= eval_episodes
    avg_length = np.average(episode_length)
    return avg_reward, avg_length


def make_exp_name(args):
    if args.gin is not None:
        extractor_name = gin.query_parameter("feature_extractor.name")

        if extractor_name == "OFE":
            ofe_unit = gin.query_parameter("OFENet.total_units")
            ofe_layer = gin.query_parameter("OFENet.num_layers")
            ofe_act = gin.query_parameter("OFENet.activation")
            ofe_block = gin.query_parameter("OFENet.block")
            ofe_act = str(ofe_act).split(".")[-1]

            ofe_name = make_ofe_name(ofe_layer, ofe_unit, ofe_act, ofe_block)
        elif extractor_name == "Munk":
            munk_size = gin.query_parameter("MunkNet.internal_states")
            ofe_name = "Munk_{}".format(munk_size)
        else:
            raise ValueError("invalid extractor name {}".format(extractor_name))
    else:
        ofe_name = "raw"

    env_name = args.env.split("-")[0]
    exp_name = "{}_{}_{}".format(env_name, args.policy, ofe_name)

    if args.name is not None:
        exp_name = exp_name + "_" + args.name

    return exp_name


def make_policy(policy, env_name, extractor, units=256):
    env = gym.make(env_name)

    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.shape[0]
    max_action = float(env.action_space.high[0])

    n_units = [units, units]

    if policy == "SAC":
        scale_reward = SAC.get_default_scale_reward(env_name)
        policy = SAC.SAC(state_dim, action_dim, max_action, feature_extractor=extractor, scale_reward=scale_reward,
                         actor_units=n_units, q_units=n_units, v_units=n_units)
    elif policy == "DDPG":
        policy = DDPG.DDPG(state_dim, action_dim, max_action, feature_extractor=extractor)
    elif policy == "TD3":
        policy = TD3.TD3(state_dim, action_dim, max_action, layer_units=(400, 300), feature_extractor=extractor)
    elif policy == "TD3small":
        policy = TD3.TD3(state_dim, action_dim, max_action, layer_units=(256, 256), feature_extractor=extractor)
    else:
        raise ValueError("invalid policy {}".format(policy))

    return policy




@gin.configurable
def feature_extractor(env_name, dim_state, dim_action,wta=0,index_k=0,finalnode=0, name=None, skip_action_branch=False):

    if name == "OFE":
        target_dim = get_target_dim(env_name)
        extractor = OFENet(dim_state=dim_state,wta=wta,index_k=index_k, dim_action=dim_action,finalnode = finalnode,
                           dim_output=target_dim, skip_action_branch=skip_action_branch)
    elif name == "Munk":
        extractor = MunkNet(dim_state=dim_state, dim_action=dim_action)
    else:
        extractor = DummyFeatureExtractor(dim_state=dim_state, dim_action=dim_action)

    return extractor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="DDPG")
    parser.add_argument("--env", default="HalfCheetah-v2")
    parser.add_argument("--seed", default=0, type=int)
    parser.add_argument("--steps", default=1020000, type=int) # 1000000
    parser.add_argument("--sac-units", default=256, type=int)
    parser.add_argument("--batch_size", default=256, type=int)
    parser.add_argument("--gin", default=None)
    parser.add_argument("--name", default=None, type=str)
    parser.add_argument("--force", default=False, action="store_true",
                        help="remove existed directory")
    parser.add_argument("--dir-root", default="output", type=str)
    parser.add_argument("--wta", default=0, type=int,
                        help="wta or not(0,1)")
    parser.add_argument("--finalnode", default=0, type=float)                    
    parser.add_argument("--indexk", default=0, type=float,
                        help="wta ratio")
    parser.add_argument("--gpu", default=0, type=int,
                        help="gpu(0,1,2,3)")

    args = parser.parse_args()


    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu)


    filename = open(str(args.env)+'_'+str(args.policy)+'_seed'+str(args.seed)+'_wta_'+str(args.wta)+'_indexk_'+str(args.indexk)+'_node_'+str(args.finalnode)+'.txt', 'w')
    # CONSTANTS
    if args.gin is not None:
        gin.parse_config_file(args.gin)

    max_steps = args.steps
    summary_freq = 1000 # 1000
    eval_freq = 5000 #5000
    random_collect = 10000 #10000 

    if eval_freq % summary_freq != 0:
        sys.exit(-1)

    env_name = args.env
    policy_name = args.policy
    batch_size = args.batch_size
    seed = args.seed


    env = gym.make(env_name)
    eval_env = gym.make(env_name)

    # Set seeds
    env.seed(seed)
    eval_env.seed(seed + 1000)
    # tf.set_random_seed(args.seed)
    np.random.seed(seed)

    dim_state = env.observation_space.shape[0]
    dim_action = env.action_space.shape[0]

    extractor = feature_extractor(env_name, dim_state, dim_action,
                                    wta=args.wta,index_k=args.indexk,finalnode=args.finalnode)

    # Makes a summary writer before graph construction
    # https://github.com/tensorflow/tensorflow/issues/26409

    policy = make_policy(policy=policy_name, env_name=env_name, extractor=extractor, units=args.sac_units)

    replay_buffer = replay.ReplayBuffer(state_dim=dim_state, action_dim=dim_action, capacity=1000000)



    total_timesteps = np.array(0, dtype=np.int32)
    episode_timesteps = 0
    episode_return = 0
    state = env.reset()


    for i in range(random_collect):
        action = env.action_space.sample()
        next_state, reward, done, _ = env.step(action)

        episode_return += reward
        episode_timesteps += 1
        total_timesteps += 1

        done_flag = done
        if episode_timesteps == env._max_episode_steps:
            done_flag = False

        replay_buffer.add(state=state, action=action, next_state=next_state, reward=reward, done=done_flag)
        state = next_state

        if done:
            state = env.reset()
            episode_timesteps = 0
            episode_return = 0

    # pretraining
    for i in range(random_collect):
        sample_states, sample_actions, sample_next_states, sample_rewards, sample_dones = replay_buffer.sample(
            batch_size=batch_size)
        extractor.train(sample_states, sample_actions, sample_next_states, sample_rewards, sample_dones)

    state = np.array(state, dtype=np.float32)
    prev_calc_time = time.time()
    prev_calc_step = random_collect

    for cur_steps in range(random_collect + 1, max_steps + 1):
        action = policy.select_action_noise(state)
        action = action.clip(env.action_space.low, env.action_space.high)

        next_state, reward, done, _ = env.step(action)
        episode_timesteps += 1
        episode_return += reward
        total_timesteps += 1

        done_flag = done

        # done is valid, when an episode is not finished by max_step.
        if episode_timesteps == env._max_episode_steps:
            done_flag = False

        replay_buffer.add(state=state, action=action, next_state=next_state, reward=reward, done=done_flag)
        state = next_state

        if done:
            state = env.reset()

            # print('done / cur_steps {:8d} | loss/exploration_return {:8.2f} '.format(cur_steps, episode_return))
            
#            tf.summary.scalar(name="loss/exploration_steps", data=episode_timesteps,
#                              description="Exploration Episode Length")
#            tf.summary.scalar(name="loss/exploration_return", data=episode_return,
#                              description="Exploration Episode Return")
            # filename.write('done / loss/exploration_steps'+'  '+str(episode_timesteps)+'  loss/exploration_return'+str(episode_return)+'\n')

            episode_timesteps = 0
            episode_return = 0

        sample_states, sample_actions, sample_next_states, sample_rewards, sample_dones = replay_buffer.sample(
            batch_size=batch_size)
        extractor.train(sample_states, sample_actions, sample_next_states, sample_rewards, sample_dones)

        policy.train(replay_buffer, batch_size=batch_size)

        if cur_steps % eval_freq == 0:
            duration = time.time() - prev_calc_time
            duration_steps = cur_steps - prev_calc_step
            throughput = duration_steps / float(duration)

#            logger.info("Throughput {:.2f}   ({:.2f} secs)".format(throughput, duration))

            cur_evaluate, average_length = evaluate_policy(eval_env, policy)
            print(' cur_steps {:8d}  |  loss/evaluate_return {:8.2f} | loss/evaluate_steps{:8.2f}  '.format(cur_steps,cur_evaluate, average_length))
            
#            tf.summary.scalar(name="loss/evaluate_return", data=cur_evaluate,
#                              description="Evaluate for test dataset")
#            tf.summary.scalar(name="loss/evaluate_steps", data=average_length,
#                              description="Step length during evaluation")
#            tf.summary.scalar(name="throughput", data=throughput, description="Throughput. Steps per Second.")
            
            filename.write('cur_steps'+' '+str(cur_steps)+'loss/evaluate_return'+'  '+str(cur_evaluate)+'  loss/evaluate_steps'+str(average_length)+'  throughput'+str(throughput)+'\n')

            prev_calc_time = time.time()
            prev_calc_step = cur_steps
    filename.close()

        # store model
        # checkpoint_manager.save(checkpoint_number=tf.constant(cur_steps, dtype=tf.int64))


if __name__ == "__main__":

    main()
