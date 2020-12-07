__author__ = 'hsfang'
__version__ = '1.0'
# Interface for accessing the GraspNet-1Billion dataset. 
# Description and part of the codes modified from MSCOCO api

# GraspNet is an open project for general object grasping that is continuously enriched. 
# Currently we release GraspNet-1Billion, a large-scale benchmark for general object grasping, 
# as well as other related areas (e.g. 6D pose estimation, unseen object segmentation, etc.).
# graspnetapi is a Python API that # assists in loading, parsing and visualizing the 
# annotations in GraspNet. Please visit https://graspnet.net/ for more information on GraspNet, 
# including for the data, paper, and tutorials. The exact format of the annotations
# is also described on the GraspNet website. For example usage of the graspnetapi
# please see graspnetapi_demo.ipynb. In addition to this API, please download both
# the GraspNet images and annotations in order to run the demo.

# An alternative to using the API is to load the annotations directly
# into Python dictionary
# Using the API provides additional utility functions. Note that this API
# supports both *grasping* and *6d pose* annotations. In the case of
# 6d poses not all functions are defined (e.g. collisions are undefined).

# The following API functions are defined:
#  GraspNet             - GraspNet api class that loads GraspNet annotation file and prepare data structures.
#  getSceneIds          - Get scene ids that satisfy given filter conditions.
#  getObjIds            - Get obj ids that satisfy given filter conditions.
#  getDataIds           - Get data ids that satisfy given filter conditions.
#  loadGraspLabels      - Load grasp labels with the specified object ids.
#  loadObjModels        - Load object 3d mesh model with the specified object ids.
#  loadCollisionLabels  - Load collision labels with the specified scene ids.
#  loadData             - Load data path with the specified data ids.
#  showObjGrasp         - Save visualization of the grasp pose of specified object ids.
#  showSceneGrasp       - Save visualization of the grasp pose of specified scene ids.
#  show6DPose           - Save visualization of the 6d pose of specified scene ids, project obj models onto pointcloud
# Throughout the API "ann"=annotation, "obj"=object, and "img"=image.

# GraspNet Toolbox.      version 1.0
# Data, paper, and tutorials available at:  https://graspnet.net/
# Code written by Hao-Shu Fang, 2020.
# Licensed under the none commercial CC4.0 license [see https://graspnet.net/about]

import os
import numpy as np
from tqdm import tqdm

def _isArrayLike(obj):
    return hasattr(obj, '__iter__') and hasattr(obj, '__len__')

class GraspNet():
    def __init__(self, root, camera='kinect', split='train'):
        assert camera in ['kinect','realsense'], 'camera should be kinect or realsense'
        assert split in ['train','train1','train2','train3','train4','test','test_seen','test_similar','test_novel'], 'split should be train/test/test_seen/test_similar/test_novel'
        self.root = root
        self.camera = camera
        self.split = split
        self.collisionLabels = {}

        if split == 'train':
            self.sceneIds = list( range(100) )
        elif split == 'train1':
            self.sceneIds = list( range(25) )
        elif split == 'train2':
            self.sceneIds = list( range(25,50) )
        elif split == 'train3':
            self.sceneIds = list( range(50,75) )
        elif split == 'train4':
            self.sceneIds = list( range(75,100) )
        elif split == 'test':
            self.sceneIds = list( range(100,190) )
        elif split == 'test_seen':
            self.sceneIds = list( range(100,130) )
        elif split == 'test_similar':
            self.sceneIds = list( range(130,160) )
        elif split == 'test_novel':
            self.sceneIds = list( range(160,190) )

        # self.sceneIds = [0]
        self.rgbPath = []
        self.depthPath = []
        self.segLabelPath = []
        self.metaPath = []
        self.sceneName = []
        for i in tqdm(self.sceneIds, desc = 'Loading data path...'):
            for img_num in range(256):
                self.rgbPath.append(os.path.join(root,'scenes', 'scene_'+str(i).zfill(4), camera, 'rgb', str(img_num).zfill(4)+'.png'))
                self.depthPath.append(os.path.join(root,'scenes', 'scene_'+str(i).zfill(4), camera, 'depth', str(img_num).zfill(4)+'.png'))
                self.segLabelPath.append(os.path.join(root, 'scenes', 'scene_'+str(i).zfill(4), camera, 'label', str(img_num).zfill(4)+'.png'))
                self.metaPath.append(os.path.join(root, 'scenes', 'scene_'+str(i).zfill(4), camera, 'meta', str(img_num).zfill(4)+'.mat'))
                self.sceneName.append('scene_'+str(i).zfill(4))

        
        self.objIds = self.getObjIds(self.sceneIds)

    def __len__(self):
        return len(self.depthPath)

    def getSceneIds(self, objIds=None):
        # get scene ids that contains **all** the given objects
        if objIds is None:
            return self.sceneIds

        assert _isArrayLike(objIds) or isinstance(objIds,int), 'objIds must be integer or a list/numy array of integers'
        objIds = objIds if _isArrayLike(objIds) else [objIds]
        sceneIds = []
        for i in self.sceneIds:
            f = open(os.path.join(self.root,'scenes', 'scene_'+str(i).zfill(4), 'object_id_list.txt'))
            idxs = [int(line.strip()) for line in f.readlines()]
            check = all(item in idxs for item in objIds)
            if check:
                sceneIds.append(i)

        return sceneIds

    def getObjIds(self, sceneIds=None):
        # get object ids in the given scenes
        if sceneIds is None:
            return self.objIds

        assert _isArrayLike(sceneIds) or isinstance(sceneIds,int), 'sceneIds must be integer or a list/numy array of integers'
        sceneIds = sceneIds if _isArrayLike(sceneIds) else [sceneIds]
        objIds = []
        for i in sceneIds:
            f = open(os.path.join(self.root,'scenes', 'scene_'+str(i).zfill(4), 'object_id_list.txt'))
            idxs = [int(line.strip()) for line in f.readlines()]
            objIds = list(set(objIds+idxs))

        return objIds


    def getDataIds(self, sceneIds=None):
        # get index for datapath that contains the given scenes
        if sceneIds is None:
            return list( range(len(self.sceneName)) )

        ids = []
        for i in sceneIds:
            indexPosList = [ j for j in range(0,len(self.sceneName),256) if self.sceneName[j] == 'scene_'+str(i).zfill(4) ]
        for idx in indexPosList:
            ids.extend([j for j in range(idx, idx+256)])

        return ids


    def loadGraspLabels(self, objIds=None, retrun_collision=False):
        # load object-level grasp labels of the given obj ids
        objIds = self.objIds if objIds is None else objIds
        assert _isArrayLike(objIds) or isinstance(objIds,int), 'objIds must be integer or a list/numy array of integers'
        objIds = objIds if _isArrayLike(objIds) else [objIds]
        graspLabels = {}
        for i in tqdm(objIds, desc='Loading grasping labels...'):
            file = np.load(os.path.join(self.root, 'grasp_label', '{}_labels.npz'.format(str(i).zfill(3))))
            if retrun_collision:
                graspLabels[i] = (file['points'].astype(np.float32), file['offsets'].astype(np.float32), file['scores'].astype(np.float32), file['collision'].astype(np.bool))
            else:
                graspLabels[i] = (file['points'].astype(np.float32), file['offsets'].astype(np.float32), file['scores'].astype(np.float32))

        return graspLabels

    def loadObjModels(self, objIds=None):
        # load object 3D models of the given obj ids
        import open3d as o3d
        objIds = self.objIds if objIds is None else objIds
        assert _isArrayLike(objIds) or isinstance(objIds,int), 'objIds must be integer or a list/numy array of integers'
        objIds = objIds if _isArrayLike(objIds) else [objIds]
        models = []
        for i in tqdm(objIds, desc = 'Loading objects...'):
            plyfile = os.path.join(self.root, 'models', '%03d'%i, 'nontextured.ply')
            models.append(o3d.io.read_point_cloud(plyfile))

        return models

    def loadObjTrimesh(self, objIds=None):
        # load object 3D trimesh of the given obj ids
        import trimesh
        objIds = self.objIds if objIds is None else objIds
        assert _isArrayLike(objIds) or isinstance(objIds,int), 'objIds must be integer or a list/numy array of integers'
        objIds = objIds if _isArrayLike(objIds) else [objIds]
        models = []
        for i in tqdm(objIds, desc = 'Loading objects...'):
            plyfile = os.path.join(self.root, 'models', '%03d'%i, 'nontextured.ply')
            models.append(trimesh.load(plyfile))

        return models

    def loadCollisionLabels(self, sceneIds=None):
        # load scene-level collision labels given scene ids
        sceneIds = self.sceneIds if sceneIds is None else sceneIds
        assert _isArrayLike(sceneIds) or isinstance(sceneIds,int), 'sceneIds must be integer or a list/numy array of integers'
        sceneIds = sceneIds if _isArrayLike(sceneIds) else [sceneIds]
        collisionLabels = {}
        for sid in tqdm(sceneIds, desc = 'Loading collision labels...'):
            labels = np.load(os.path.join(self.root, 'collision_label', 'scene_'+str(sid).zfill(4),  'collision_labels.npz'))
            collisionLabel = []
            for j in range(len(labels)):
                collisionLabel.append(labels['arr_{}'.format(j)])
            collisionLabels['scene_'+str(sid).zfill(4)] = collisionLabel

        return collisionLabels

    def loadData(self, ids=None):
        # return data and anno path of given indexes
        if ids is None:
            return (self.rgbPath, self.depthPath, self.segLabelPath, self.metaPath, self.sceneName)

        if isinstance(ids,int):
            return (self.rgbPath[ids], self.depthPath[ids], self.segLabelPath[ids], self.metaPath[ids], self.sceneName[ids])

        return ( [self.rgbPath[id] for id in ids],
                    [self.depthPath[id] for id in ids],
                    [self.segLabelPath[id] for id in ids],
                    [self.metaPath[id] for id in ids],
                    [self.sceneName[id] for id in ids] )

    def showObjGrasp(self, objIds=[], numGrasp=10, th=0.5, saveFolder='save_fig', show=False):

        from .vis import visObjGrasp
        objIds = objIds if _isArrayLike(objIds) else [objIds]
        if len(objIds) == 0:
            print('You need specify object ids.')
            return 0

        for obj_id in objIds:
            visObjGrasp(self.root, obj_id, num_grasp=numGrasp, th=th, save_folder=saveFolder, show=show)

    def showSceneGrasp(self, sceneIds=[], format='6d', numGrasp=2, th=0.5, saveFolder='save_fig', show=False):

        from .vis import visAnno
        sceneIds = sceneIds if _isArrayLike(sceneIds) else [sceneIds]
        if len(sceneIds) == 0:
            print('You need specify scene ids.')
            return 0

        for scene_id in sceneIds:
            scene_name = 'scene_'+str(scene_id).zfill(4)
            if format == '6d':
                visAnno(self.root, scene_name, 0, self.camera, num_grasp=numGrasp, th=th, align_to_table=True, max_width=0.08, save_folder=saveFolder, show=show)
            elif format == 'rect':
                pass
                # @TODO minghao
            else:
                print('format should be 6d or rect')
                return 0


    def show6DPose(self, sceneIds, saveFolder='save_fig', show=False):

        from .vis import vis6D
        sceneIds = sceneIds if _isArrayLike(sceneIds) else [sceneIds]
        if len(sceneIds) == 0:
            print('You need specify scene ids.')
            return 0

        for scene_id in sceneIds:
            scene_name = 'scene_'+str(scene_id).zfill(4)
            vis6D(self.root, scene_name, 0, self.camera, align_to_table=True, save_folder=saveFolder, show=show)


