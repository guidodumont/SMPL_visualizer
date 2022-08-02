################################################################################
# File: \vis_double.py                                                         #
# Created Date: Sunday July 17th 2022                                          #
# Author: climbingdaily                                                        #
# -----                                                                        #
# Modified By: the developer climbingdaily at yudidai@stu.xmu.edu.cn           #
# https://github.com/climbingdaily                                             #
# -----                                                                        #
# Copyright (c) 2022 yudidai                                                   #
# -----                                                                        #
# HISTORY:                                                                     #
################################################################################

import re
import numpy as np
import configargparse
import open3d as o3d
from scipy.spatial.transform import Rotation as R
from util import o3dvis
import matplotlib.pyplot as plt
import torch
import os

from smpl import SMPL, poses_to_vertices
from util import load_data_remote, generate_views, load_scene, images_to_video

view = {
	"trajectory" : 
	[
		{
			"boundingbox_max" : [ 68.419929504394531, 39.271018981933594, 11.569537162780762 ],
			"boundingbox_min" : [ -11.513210296630859, -35.915927886962891, -2.4593989849090576 ],
			"field_of_view" : 60.0,
			"front" : [ 0.28886465410454343, -0.85891896928352873, 0.42286571841896009 ],
			"lookat" : [ 0.76326815774101275, 3.2896492351216851, 0.040108816664781548 ],
			"up" : [ -0.12866047345544837, 0.40286011796513765, 0.90617338734004726 ],
			"zoom" : 0.039999999999999994
		}
	],
}

pt_color = plt.get_cmap("tab20")(1)[:3]
smpl_color = plt.get_cmap("tab20")(3)[:3]
gt_smpl_color = plt.get_cmap("tab20")(5)[:3]
pred_smpl_color = plt.get_cmap("tab20")(7)[:3]

def vertices_to_head(vertices, index = 15):
    smpl = SMPL()
    return smpl.get_full_joints(torch.FloatTensor(vertices))[..., index, :]

def load_pred_smpl(file_path, start=0, end=-1, pose='pred_rotmats', trans=None, remote=False):
    import pickle

    pred_vertices = np.zeros((0, 6890, 3))
    load_data_class = load_data_remote(remote)
    humans = load_data_class.load_pkl(file_path)

    for k,v in humans.items():    
        pred_pose = v[pose]
        if end == -1:
            end = pred_pose.shape[0]
        pred_pose = pred_pose[start:end]
        pred_vertices = np.concatenate((pred_vertices, poses_to_vertices(pred_pose, trans)))

    return pred_vertices

def get_head_global_rots(pose):
    if pose.shape[1] == 72:
        pose = pose.reshape(-1, 24, 3)

    head_parents = [0, 3, 6, 9, 12, 15]
    head_rots = np.eye(3)
    for r in head_parents[::-1]:
        head_rots = R.from_rotvec(pose[:, r]).as_matrix() @ head_rots
    head_rots = head_rots @ np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]]).T
    return head_rots

def load_pkl_vis(humans, start=0, end=-1, pred_file_path=None, remote=False):
    """
    It takes in the human dictionary, and returns a list of vertices, a list of predicted vertices, a
    list of point clouds, and a list of indices
    
    Args:
      humans: the dictionary containing the data
      start: the first frame to load. Defaults to 0
      end: the last frame to be rendered
      pred_file_path: the path to the predicted SMPL model
      remote: whether the data is stored on a remote server or not. Defaults to False
    """

    point_valid_idx = []
    verts_list = []
    point_clouds = np.array([[0,0,0]])
    pred_s_vert = None

    first_person = humans['first_person']
    pose = first_person['pose'].copy()
    trans = first_person['mocap_trans'].copy()

    f_vert = poses_to_vertices(pose)

    # load first person
    if 'lidar_traj' in first_person:
        lidar_traj = first_person['lidar_traj'][:, 1:4]
        head = vertices_to_head(f_vert, 15)
        root = vertices_to_head(f_vert, 0)
        head_to_root = (root - head).numpy()
        
        head_rots = get_head_global_rots(pose)

        lidar_to_head =  head[0] - lidar_traj[0] + trans[0] 
        lidar_to_head = head_rots @ head_rots[0].T @ lidar_to_head.numpy()

        trans = lidar_traj + lidar_to_head + head_to_root
        # trans = lidar_traj[:, 1:4]
    
    f_vert += np.expand_dims(trans.astype(np.float32), 1)

    verts_list.append(f_vert)
    print(f'[SMPL MODEL] First person loaded')

    # load second person
    if 'second_person' in humans:
        second_person = humans['second_person']    
        pose = second_person['pose'].copy()
        trans = second_person['mocap_trans'].copy()
        s_vert = poses_to_vertices(pose, trans)
        verts_list.append(s_vert)
        print(f'[SMPL MODEL] Second person loaded')

        # load optimized person
        if 'opt_pose' in first_person:
            pose = first_person['opt_pose'].copy()
            trans = first_person['opt_trans'].copy()
            vert = poses_to_vertices(pose, trans)
            verts_list.append(vert)
            print(f'[SMPL MODEL] First optmized person loaded')
            
        if 'opt_pose' in second_person:
            pose = second_person['opt_pose'].copy()
            trans = second_person['opt_trans'].copy()
            vert = poses_to_vertices(pose, trans)
            verts_list.append(vert)
            print(f'[SMPL MODEL] Second optmized person loaded')

        if 'point_clouds' in second_person:
            point_clouds = second_person['point_clouds']
            ll = second_person['point_frame']
            print(f'[PointCloud] Second point cloud loaded')

        else:
            ll = []

        point_valid_idx = [np.where(humans['frame_num'] == l)[0][0] for l in ll ]

    if pred_file_path is not None :
        pred_s_vert = load_pred_smpl(pred_file_path, trans=trans[point_valid_idx], remote=remote)
        print(f'[SMPL MODEL] Predicted person loaded')

    return verts_list, pred_s_vert, point_clouds, point_valid_idx

def vis_pt_and_smpl(smpl_list, pc, pc_idx, vis, pred_smpl_verts=None, extrinsics=None, video_name=None, freeviewpoint=False):

    # assert smpl_list[0].shape[0] == smpl_list[1].shape[0], "Groundtruth Data Shape are not compatible"
    pointcloud = o3d.geometry.PointCloud()
    smpl_geometries = []
    pred_smpl = o3d.io.read_triangle_mesh('.\\smpl\\sample.ply')
    for i in smpl_list:
        smpl_geometries.append(o3d.io.read_triangle_mesh('.\\smpl\\sample.ply')) # a ramdon SMPL mesh

    init_param = False
    # extrinsic = np.eye(4)
    vis.img_save_count = 0
    image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'temp_{video_name}')

    for i in range(smpl_list[0].shape[0]):

        # load data
        if i in pc_idx:
            pointcloud.points = o3d.utility.Vector3dVector(pc[pc_idx.index(i)])
            if pred_smpl_verts is not None:
                pred_smpl.vertices = o3d.utility.Vector3dVector(pred_smpl_verts[pc_idx.index(i)])
                pred_smpl.paint_uniform_color(plt.get_cmap("tab20")(7)[:3])
                pred_smpl.compute_vertex_normals()
        else:
            pointcloud.points = o3d.utility.Vector3dVector(np.array([[0,0,0]]))
            pred_smpl.vertices = o3d.utility.Vector3dVector(np.asarray(pred_smpl.vertices) * 0)
            pred_smpl.compute_vertex_normals()

        # color
        pointcloud.paint_uniform_color(pt_color)

        for idx, smpl in enumerate(smpl_geometries):
            smpl.vertices = o3d.utility.Vector3dVector(smpl_list[idx][i])
            smpl.paint_uniform_color(plt.get_cmap("tab20")(idx*2 + 3)[:3])
            smpl.compute_vertex_normals()
        

        if extrinsics is not None:
            # vis.set_view(view_list[i])
            if i > 0 and freeviewpoint:
                camera_pose = vis.get_camera()
                # relative_pose = extrinsics[i] @ np.linalg.inv(extrinsics[i-1])
                relative_trans = -extrinsics[i][:3, :3].T @ extrinsics[i][:3, 3] + extrinsics[i-1][:3, :3].T @ extrinsics[i-1][:3, 3]
                
                camera_positon = -(camera_pose[:3, :3].T @ camera_pose[:3, 3])
                camera_pose[:3, 3] = -(camera_pose[:3, :3] @ (camera_positon + relative_trans))
                vis.init_camera(camera_pose)
            else:
                vis.init_camera(extrinsics[i])   
                
        # add to visualization
        if not init_param:
            vis.add_geometry(pointcloud, reset_bounding_box = False)  
            for smpl in smpl_geometries:
                vis.add_geometry(smpl, reset_bounding_box = False)  
            if pred_smpl is not None:
                vis.add_geometry(pred_smpl, reset_bounding_box = False)  
            vis.change_pause_status()
            init_param = True

        else:
            vis.vis.update_geometry(pointcloud) 
            if pred_smpl is not None:
                vis.vis.update_geometry(pred_smpl)  
            for smpl in smpl_geometries:
                vis.vis.update_geometry(smpl)    
 
        vis.save_imgs(image_dir)
        
        vis.waitKey(20, helps=False)
            
    images_to_video(image_dir, video_name, delete=True)

    for g in smpl_geometries:
        vis.remove_geometry(g)

if __name__ == '__main__':    
    import config
    parser = configargparse.ArgumentParser()
    parser.add_argument("--start", '-S', type=int, default=-2)
    parser.add_argument("--end", '-e', type=int, default=-2)
    parser.add_argument("--scene_path", '-s', type=str,default=None)
    # parser.add_argument("--remote", '-r', action='store_true',
    #                     help='If the file in from remote machine')
    
    parser.add_argument("--smpl_file_path", '-F', type=str, default=None)
    parser.add_argument("--pred_file_path", '-P', type=str, default=None)
    parser.add_argument("--viewpoint_type", '-V', type=str, default=None)

    args, opts = parser.parse_known_args()

    start = config.start if args.start == -2 else args.start
    end = config.end if args.end == -2 else args.end
    scene_path = config.scene_path if args.scene_path is None else args.scene_path
    is_remote = True if '--remote' in opts else config.remote

    smpl_file_path = config.smpl_file_path if args.smpl_file_path is None else args.smpl_file_path
    pred_file_path = config.pred_file_path if args.pred_file_path is None else args.pred_file_path
    viewpoint_type = config.viewpoint_type if args.viewpoint_type is None else args.viewpoint_type

    vis = o3dvis("First view", width=1280, height=720)
    load_data_class = load_data_remote(is_remote)

    scene = load_scene(vis, scene_path)
    if not scene.has_points():
        scene = load_scene(vis, scene_path, load_data_class = load_data_class)


    print(f'Load pkl in {smpl_file_path}')

    humans = load_data_class.load_pkl(smpl_file_path)

    smpl_list, pred_smpl_b, pc, pc_idx = load_pkl_vis(
        humans, start, end, pred_file_path, remote=is_remote)

    # lidar_view = generate_views(humans['first_person']['lidar_traj']
    #                      [:, 1:4], humans['first_person']['lidar_traj'][:, 4:8])

    scene_name = os.path.basename(scene_path).split('.')[0]

    FPV, fextrinsic = generate_views(humans['first_person']['lidar_traj']
                         [:, 1:4], get_head_global_rots(humans['first_person']['pose']))
                         
    SPV, sextrinsic = generate_views(vertices_to_head(
        smpl_list[1]) + np.array([0, 0, 0.2]), get_head_global_rots(humans['second_person']['pose']))

    if viewpoint_type == 'first':
        vis_pt_and_smpl(smpl_list, pc, pc_idx, vis,
                        pred_smpl_verts=pred_smpl_b, extrinsics=fextrinsic, 
                        video_name = scene_name + '_FPV')

    elif viewpoint_type == 'second':
        vis_pt_and_smpl(smpl_list, pc, pc_idx, vis,
                        pred_smpl_verts=pred_smpl_b, extrinsics=sextrinsic, 
                        video_name = scene_name + '_SPV')

    elif viewpoint_type == 'third':        
        vis_pt_and_smpl(smpl_list, pc, pc_idx, vis,
                        pred_smpl_verts=pred_smpl_b, extrinsics=fextrinsic, 
                        video_name = scene_name + '_TPV', freeviewpoint=True)

    else:

        vis_pt_and_smpl(smpl_list, pc, pc_idx, vis,
                        pred_smpl_verts=pred_smpl_b, extrinsics=fextrinsic, 
                        video_name = scene_name + '_FPV')
        vis_pt_and_smpl(smpl_list, pc, pc_idx, vis,
                        pred_smpl_verts=pred_smpl_b, extrinsics=sextrinsic, 
                        video_name = scene_name + '_SPV')
        vis_pt_and_smpl(smpl_list, pc, pc_idx, vis,
                        pred_smpl_verts=pred_smpl_b, extrinsics=fextrinsic, 
                        video_name = scene_name + '_TPV', freeviewpoint=True)