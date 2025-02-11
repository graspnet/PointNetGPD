	# Use tensors to speed up loading data onto the GPU during training.
import numpy as np
import open3d as o3d
import json

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data as torchdata
import torch.multiprocessing
import sys
from graspnetAPI import GraspNet, GraspNetEval, GraspGroup
#torch.multiprocessing.set_start_method('spawn')
from grasptoolbox.grasp_sampling.gen_grasp_cloud import estimate_normals, estimate_darboux_frame
#from grasptoolbox.grasp_sampling.gen_grasp_image import transform_cloud_to_image
from grasptoolbox.collision_detection.collision_detector import ModelFreeCollisionDetector

from model.dataset import *
from model.pointnet import PointNetCls, DualPointNetCls
#from json_dataset import JsonDataset
#from network import Net, NetCCFFF
from tqdm import tqdm
import os
import time
import cv2


height = 0.02
depth_base = 0.02
grasp_depth = 0.02
grasp_width = 0.08
num_sample = 2000
grasp_points_num = 750
DUMP_DIR = './dump/'
CAMERA = 'kinect'

#g = GraspNet('/home/minghao/graspnet/', camera='kinect', split='test')
g = GraspNet('/ssd1/graspnet/', camera=CAMERA, split='test')
sceneIds = g.getSceneIds()

'''
is_resume = 0
if args.load_model and args.load_epoch != -1:
    is_resume = 1

if is_resume or args.mode == 'test':
    model = torch.load(args.load_model, map_location='cuda:{}'.format(args.gpu))
    model.device_ids = [args.gpu]
    print('load model {}'.format(args.load_model))
else:
    model = PointNetCls(num_points=grasp_points_num, input_chann=point_channel, k=3)
'''


input_channels = 3
gpu = 3
#model = Net(input_channels)
#model = PointNetCls(num_points=750, input_chann=input_channels, k=3)
model = torch.load("assets/learned_models/main_lr_5.model", map_location='cuda:{}'.format(gpu))
model.device_ids = [gpu]
torch.cuda.set_device(gpu)
model = model.cuda()
model.eval()


def flat(nums):
    res = []
    for i in nums:
        if isinstance(i, list):
            res.extend(flat(i))
        else:
            res.append(i)
    return res

for sceneId in range(100,101):
    for i in tqdm(range(256)):
        t1 = time.time()
        cloud = g.loadScenePointCloud(sceneId, CAMERA, i, align=False, format = 'open3d', use_workspace=True)
        fullcloud = g.loadScenePointCloud(sceneId, CAMERA, i, align=False, format = 'open3d', use_workspace=True)
        downpc = cloud.voxel_down_sample(voxel_size=0.005)
        sparsepc = cloud.voxel_down_sample(voxel_size=0.03)
        points = np.array(downpc.points).astype(np.float32)
        rgbs = np.array(downpc.colors).astype(np.float32)
        t2 = time.time()
        print("time read data: ",t2-t1)
        normals = estimate_normals(points, k=10, align_direction=False, ret_cloud=False)
        idx = np.random.choice(len(points), num_sample)
        grasp_points = points[idx]
        grasp_normals = normals[idx]
        grasp_frames = estimate_darboux_frame(grasp_points, grasp_normals, points, normals, dist_thresh=0.01)
        
        t3 = time.time()
        print("time process frame: ",t3-t2)
        
        points_centered = points[np.newaxis,:,:] - grasp_points[:,np.newaxis,:]

        targets = np.matmul(points_centered, grasp_frames) #(num_sample, num_point, 3)
        t4 = time.time()
        print("time transform points: ",t4-t3)

        feats = []
        grasp_group = []

        for j, ind in enumerate(range(targets.shape[0])):
            target = targets[ind]
            mask1 = ((target[:,2]>-height) & (target[:,2]<height))
            mask2 = ((target[:,0]<grasp_depth) & (target[:,0]>-depth_base))
            mask3 = ((target[:,1]>-grasp_width/2) & (target[:,1]<grasp_width/2))
            mask = (mask1 & mask2 & mask3)
            pc = target[mask]
            if len(pc) == 0:
                continue
            pc = estimate_normals(pc, k=20, align_direction=True, ret_cloud=True)
            pc.colors = o3d.utility.Vector3dVector(rgbs[mask])
            #o3d.io.write_point_cloud('assets/graspnet/'+str(i)+'_'+str(j)+'.ply', pc, write_ascii=False, compressed=True)

            #img = transform_cloud_to_image(pc)
            # cv2.imwrite('assets/'+str(i)+'_'+str(j)+'.jpg', img)
            # pc: 'open3d.open3d.geometry.PointCloud' object
            pc = np.asarray(pc.points)
            
            if len(pc) > grasp_points_num:
                pc = pc[np.random.choice(len(pc), size = grasp_points_num, replace=False)].T
            else:
                pc = pc[np.random.choice(len(pc), size = grasp_points_num, replace=True)].T

            #pc = np.zeros((90,90))
            feats.append(pc) 
            grasp_group.append(flat([1, grasp_width, height, grasp_depth, grasp_frames[j].reshape(9).tolist(), grasp_points[j].reshape(3).tolist(), -1]))
        t5 = time.time()
        print("time crop points: ",t5-t4)

        grasp_group = np.array(grasp_group)
        #print(grasp_group)
        mfcdetector = ModelFreeCollisionDetector(np.array(fullcloud.points).astype(np.float32), voxel_size=0.005)
        collision_mask = mfcdetector.detect(GraspGroup(grasp_group), approach_dist=0.03, collision_thresh=0.01)

        t6 = time.time()
        print("time collision checking: ",t6-t5)

        feats = np.array(feats)
        valid_feats = feats[~collision_mask]
        print(collision_mask.shape)
        print(valid_feats.shape)
        #print(valid_feats)
        
        inputs = torch.from_numpy(np.array(valid_feats).astype(np.float32)).float().cuda()
        #inputs = torch.from_numpy(np.array(valid_feats).astype(np.float32))
        outputs, _ = model(inputs)
        outputs = nn.Softmax(dim=1)(outputs)
        scores = outputs.data[:,1]

        final_grasps = grasp_group[~collision_mask]
        print(final_grasps.shape)
        final_grasps[:,0] = scores.detach().cpu().numpy()
        print(final_grasps.shape)

        if not os.path.exists(os.path.join(DUMP_DIR, 'scene_'+str(sceneId).zfill(4), CAMERA)):
            os.makedirs(os.path.join(DUMP_DIR, 'scene_'+str(sceneId).zfill(4), CAMERA))
        print(np.array(sparsepc.points).shape)
        print(np.array(sparsepc.colors).shape)
        # npz for vis, npy for eval
        # np.savez_compressed(os.path.join(DUMP_DIR,  'scene_'+str(sceneId).zfill(4), str(i%256).zfill(4)+'.npz'), clouds=np.array(sparsepc.points), colors=np.array(sparsepc.colors), preds=np.array(final_grasps))
        np.save(os.path.join(DUMP_DIR, 'scene_'+str(sceneId).zfill(4), CAMERA, str(i%256).zfill(4)+'.npy'),np.array(final_grasps))
        print(1111)
