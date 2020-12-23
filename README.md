# Our Model
We propose a feature extractor network for low-dimensional data to improve performance of Reinforcement Learning.
It can be combined with several off-policy algorithms such as SAC, TD3 and DDPG. Original code is available from http://www.merl.com/research/license/OFENet.

This repository contains the model implementation, RL algorithms, and hyperparameters.

## Requirement

```bash
$ conda create -n teflon python=3.6 anaconda
$ conda activate teflon
$ conda install cudatoolkit=10.0 cudnn tensorflow-gpu==2.0.0
$ pip install -r requirements.txt
```

### MuJoCo

Install MuJoCo 2.0 from the [official web site](http://www.mujoco.org/index.html).

```bash
$ mkdir ~/.mujoco
$ cd ~/.mujoco
$ wget https://www.roboti.us/download/mujoco200_linux.zip
$ unzip mujoco200_linux.zip
$ mv mujoco200_linux mujoco200
$ cp /path/to/mjkey.txt ./
$ pip install mujoco_py
```

## Examples

To train an agent with our method, run the below commands at the project root.

```bash
$ export PYTHONPATH=.
$ python3 teflon/tool/eager_main_try.py --policy SAC \
                                  --env HalfCheetah-v2 \
                                  --gin ./gins/HalfCheetah.gin \
                                  --seed 0\
                                  --wta 1\
                                  --finalnode 350\
                                  --indexk 0.7
```

If you want to combine our method with TD3 or DDPG, change the policy like

```bash
$ export PYTHONPATH=.
$ python3 teflon/tool/eager_main_try.py --policy TD3 \
                                  --env HalfCheetah-v2 \
                                  --gin ./gins/HalfCheetah.gin \
                                  --seed 0\
                                  --wta 1\
                                  --finalnode 350\
                                  --indexk 0.7
```

When you want to run an agent in another environment, change the policy and 
the hyperparameter file (.gin).

```bash
$ python3 teflon/tool/eager_main_try.py --policy SAC \
                                  --env Walker2d-v2  \
                                  --gin ./gins/Walker2d.gin \
                                  --seed 0\
                                  --wta 1\
                                  --finalnode 350\
                                  --indexk 0.7
```

When you don't specify a gin file, you train an agent with raw observations. 

```bash
$ python3 teflon/tool/eager_main_try.py --policy SAC \
                                  --env HalfCheetah-v2 \
                                  --seed 0
```

ML-SAC is trained with the below command.

```bash
$ python3 teflon/tool/eager_main_try.py --policy SAC \
                                  --env HalfCheetah-v2 \
                                  --gin ./gins/Munk.gin \
                                  --seed 0
```

## results

`eager_main_try.py` generates a corresponding txt document.
You can watch the result of an experiment.

