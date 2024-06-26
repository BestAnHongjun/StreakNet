#!/usr/bin/env3 python3
# Copyright (c) School of Artificial Intelligence, OPtics and ElectroNics(iOPEN), Northwestern PolyTechnical University. All rights reserved.
# Author: Hongjun An (Coder.AN)
# Email: an.hongjun@foxmail.com

import os
import cv2
import argparse
from loguru import logger
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt

import torch 
from torch.utils.data import DataLoader

from streaknet.exp import get_exp
from streaknet.data import StreakImageDataset, RandomNoise
from streaknet.utils import standard, hilbert, get_embedding_filter


def make_parse():
    parser = argparse.ArgumentParser("Band Pass Filter Demo.")
    parser.add_argument("-expn", "--experiment-name", type=str, default=None)
    parser.add_argument("-b", "--batch-size", type=int, default=2)
    parser.add_argument("-f", "--exp_file", default=None, type=str, help="please input your experiment description file")
    parser.add_argument("-c", "--ckpt", default=None, type=str, help="ckpt for demo")
    parser.add_argument("-l", "--lower", type=float, default=450, help="Lower bound of Band Pass Filter, MHz")
    parser.add_argument("-u", "--upper", type=float, default=550, help="Upper bound of Band Pass Filter, MHz")
    parser.add_argument("-d", "--device", type=str, default='cpu', help="Select device.")
    parser.add_argument("-p", "--path", type=str, required=True)
    parser.add_argument("-t", "--template", type=str, default=None)
    parser.add_argument("--noise", default=0, type=float)
    parser.add_argument("--save", default=False, action="store_true")
    parser.add_argument("--cache", action="store_true", default=False)
    parser.add_argument("--num_workers", type=int, default=4)
    return parser


def get_filter(args, max_len=4000):
    if args.exp_file is None:
        # 满屏扫描时间30ns，CCD分辨率2048，采样频率68.27GHz
        # 使用长度65536计算FFT，频率分辨率68.27GHz/65536=1.04MHz
        freq_resolutio = (2048 / 30) * 1000 / 65536
        lower = round(args.lower / freq_resolutio)
        upper = round(args.upper / freq_resolutio)
        filter = torch.ones((1, 1, max_len), dtype=torch.float32)
        filter[:, :, :lower] = 0
        filter[:, :, upper:] = 0
        file_name = os.path.join("StreakNet_outputs", "traditional", "bandpass_{}_{}".format(args.lower, args.upper))
        return filter, file_name
    else:
        exp = get_exp(args.exp_file)
        if not args.experiment_name:
            args.experiment_name = exp.exp_name
            
        model = exp.get_model()
        logger.info("Model Structure:\n{}".format(str(model)))
        
        file_name = os.path.join(exp.output_dir, args.experiment_name)
        if args.ckpt is None:
            ckpt_file = os.path.join(file_name, "best_ckpt.pth")
        else:
            ckpt_file = args.ckpt
        logger.info("loading checkpoint")
        loc = args.device
        ckpt = torch.load(ckpt_file, map_location=loc)
        # load the model state dict
        model.load_state_dict(ckpt["model"])
        logger.info("loaded checkpoint done.")
        
        signal_radar_filter = get_embedding_filter(model)
    
        return signal_radar_filter, file_name


def band_pass_filter_algorithm(dataset, batch_size, filter, device=torch.device('cpu'), num_workers=4):
    data_loader = DataLoader(dataset, batch_size, num_workers=num_workers, pin_memory=True)
    
    gray_img = torch.zeros((2048, dataset.nums), dtype=torch.float32).to(device)
    deep_img = torch.zeros((2048, dataset.nums), dtype=torch.float32).to(device)
    
    template = torch.tensor(dataset.template, dtype=torch.float32).to(device)[None, None, :].repeat(batch_size, 1, 1)
    template_freq = torch.fft.rfft(template, 65536, dim=2)

    for img, _, idx in tqdm(data_loader):
        img = img.to(device)
        
        img_freq = torch.fft.rfft(img, 65536, dim=2) # 只取正频率部分
        tem_freq = template_freq[:img_freq.shape[0]]
        
        # 带通滤波 & 匹配滤波
        img_freq[:, :, 4000:] = 0
        img_freq[:, :, :4000] *= filter
        match_filt = torch.absolute(torch.fft.irfft(tem_freq * img_freq, dim=2)[:, :, :2048])
        match_filt = hilbert(match_filt)
        
        # 确定最大响应及其时间
        max_resp, max_resp_index = torch.max(match_filt, dim=2)
        gray_img[:, idx[:, 0]] = max_resp.T
        
        # 计算景深
        distance = (max_resp_index * 30 * 1e-9 / 2 /2048) * 3e8 
        deep_img[:, idx[:, 0]] = distance.T
    
    # 转换为灰度值
    gray_img = standard(gray_img) * 255
    gray_img[gray_img > 255] = 255
    gray_img = gray_img.cpu().numpy().astype(np.uint8)
    deep_img = deep_img.cpu().numpy()
    
    # 抑制背景噪声
    _, mask_otsu = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    mask_adap = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 65, 2)
    mask_otsu //= 255
    mask_adap //= 255
    mask = mask_otsu * mask_adap
        
    gray_img *= mask
    deep_img *= mask

    return gray_img, deep_img, mask
    

def main(args):
    device = torch.device(args.device)
    filter, file_name = get_filter(args, 4000)
    filter = filter.to(device)
    
    transform = RandomNoise(args.noise)
    dataset = StreakImageDataset(args.path, args.template, cache=args.cache, transform=transform)

    gray_img, deep_img, mask= band_pass_filter_algorithm(
        dataset, args.batch_size, filter, 
        device=device, num_workers=args.num_workers)
        
    fig = plt.figure(figsize=(18, 8))
    x = np.arange(0, deep_img.shape[1], 1)
    z = np.arange(0, deep_img.shape[0], 1)
    x, z = np.meshgrid(x, z)
    x = x[mask == 1]
    z = z[mask == 1]
    deep_img = deep_img[mask == 1]
    
    ax1 = fig.add_subplot(2, 4, (1, 5))
    ax1.imshow(gray_img)
    
    ax2 = fig.add_subplot(2, 4, (2, 6))
    ax2.imshow(mask * 255, cmap='gray')
    
    ax3 = fig.add_subplot(2, 4, 3, projection='3d')
    ax3.scatter(x, deep_img, z, c=deep_img, cmap='viridis', s=0.1)
    ax3.set_zlim([800, 1700])
    ax3.yaxis._set_scale("log")
    ax3.set_ylim([1, 6])
    
    ax4 = fig.add_subplot(2, 4, 4)
    ax4.scatter(deep_img, z, c=deep_img, cmap='viridis', s=0.1)
    # ax4.set_xscale("log")
    # ax4.set_xlim([1, 6])
    ax4.set_ylim([800, 1700])
    
    ax5 = fig.add_subplot(2, 4, 7)
    ax5.scatter(x, deep_img, c=deep_img, cmap='viridis', s=0.1)
    # ax5.set_yscale("log")
    # ax5.set_ylim([1, 6])
    
    ax6 = fig.add_subplot(2, 4, 8)
    ax6.scatter(x, z, c=deep_img, cmap='viridis', s=0.1)
    ax6.set_ylim([800, 1700])
    
    plt.subplots_adjust(wspace=0.3)

    if args.save:
        plt.savefig(os.path.join(file_name, "band_pass_demo.png"))
    else:
        plt.show()
    

if __name__ == "__main__":
    args = make_parse().parse_args()
    main(args)
    