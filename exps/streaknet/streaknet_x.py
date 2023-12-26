#!/usr/bin/env3 python3
# Copyright (c) School of Artificial Intelligence, OPtics and ElectroNics(iOPEN), Northwestern PolyTechnical University. All righs reserved.
# Author: Hongjun An (Coder.AN)
# Email: an.hongjun@foxmail.com

import os 

from streaknet.exp import Exp as MyExp 


class Exp(MyExp):
    def __init__(self):
        super(Exp, self).__init__()
        self.depth = 1.00
        self.width = 1.00
        self.exp_name = os.path.split(os.path.realpath(__file__))[1].split(".")[0]
        