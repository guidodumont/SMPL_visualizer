################################################################################
# File: \vis_test.py                                                           #
# Created Date: Friday August 12th 2022                                        #
# Author: climbingdaily                                                        #
# -----                                                                        #
# Modified By: the developer climbingdaily at yudidai@stu.xmu.edu.cn           #
# https://github.com/climbingdaily                                             #
# -----                                                                        #
# Copyright (c) 2022 yudidai                                                   #
# -----                                                                        #
# HISTORY:                                                                     #
################################################################################

import numpy as np
import open3d as o3d
import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering
import sys
import cv2
import threading
import os
import time
from scipy.spatial.transform import Rotation as R

sys.path.append('.')
sys.path.append('..')

from menu import Menu as base_gui
from bottons import _init_left_panel

from util import load_data_remote, generate_views, load_scene as load_pts, images_to_video
from vis_smpl_scene import load_vis_data, get_head_global_rots, vertices_to_head, POSE_COLOR
from smpl import sample_path

class HUMAN_DATA:
    FOV = 'first'
    FREE_VIEW = False

    def __init__(self, is_remote):
        self.is_remote = is_remote
        self.cameras = {}

    def load(self, filename):
        load_data_class = load_data_remote(self.is_remote)
        humans = load_data_class.load_pkl(filename)
        self.vis_data_list = load_vis_data(humans)
        self.set_cameras(humans)

    def set_cameras(self, humans):
        try:
            self.cameras['first'] = generate_views(humans['first_person']['lidar_traj']
                                [:, 1:4], get_head_global_rots(humans['first_person']['pose']))
            print(f'[Camera]: First person views')
        except:
            print(f'There is no first pose in the data')


        try:
            second_verts = self.vis_data_list['humans']['Second opt_pose']
            second_pose = humans['second_person']['opt_pose']
            self.cameras['second'] = generate_views(vertices_to_head(second_verts) + np.array([0, 0, 0.2]), get_head_global_rots(second_pose))
            print(f'[Camera]: second opt. person views')
        except:
            try:
                second_verts = self.vis_data_list['humans']['Second pose']
                second_pose = humans['second_person']['pose']
                self.cameras['second'] = generate_views(vertices_to_head(second_verts) + np.array([0, 0, 0.2]), get_head_global_rots(second_pose))
                print(f'[Camera]: second person views')
            except:
                print(f'There is no second pose in the data')
    
    def get_cameras(self, FOV):
        return self.cameras[FOV.lower()]

class o3dvis(base_gui):
    PAUSE = False

    def __init__(self, width=1280, height=768, is_remote=False):
        super(o3dvis, self).__init__(width, height)
        self.COOR_INIT = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
        self.scene_name = None
        self.Human_data = HUMAN_DATA(is_remote)
        self.freeview = True
        self.POV = 'first'
        self.is_done = False
        self.names = []
        # self._init_left_panel()

    def _on_menu_show(self):
        if self.scene_name or self.Human_data:
            threading.Thread(target=self.update_thread).start()
        else:
            super(o3dvis, self)._on_menu_show()

    def load_scene(self, scene_path):
        self.window.close_dialog()
        if not os.path.isfile(scene_path):
            return
        self.scene_name = os.path.basename(scene_path).split('.')[0]
        load_pts(self, scene_path)


    def _on_load_smpl_done(self, filename):
        self.window.close_dialog()
        self.Human_data.load(filename) 

    def update_thread(self):
        """
        The function is to render the 3D point cloud and the SMPL mesh in the same window
        """
        vis_data = self.Human_data.vis_data_list
        views, extrinsics = self.Human_data.get_cameras('first')

        video_name = self.scene_name + f'_{self.POV}'
        freeviewpoint = self.freeview

        pointcloud = o3d.geometry.PointCloud()
        smpl_geometries = []
        smpl_materials = []
        human_data = vis_data['humans']
        points = vis_data['point cloud'][0]
        indexes = vis_data['point cloud'][1]

        for i in human_data:
            smpl = o3d.io.read_triangle_mesh(sample_path)
            smpl_geometries.append(smpl) # a ramdon SMPL mesh

        self.img_save_count = 0
        video_name += time.strftime("-%Y-%m-%d_%H-%M", time.localtime())
        image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'temp_{video_name}')
        keys = list(human_data.keys())
        init_param = False

        for i in range(human_data[keys[0]].shape[0]):
            time.sleep(0.1)
            if i in indexes:
                index = indexes.index(i)
                pointcloud.points = o3d.utility.Vector3dVector(points[index])
            else:
                index = -1
                pointcloud.points = o3d.utility.Vector3dVector(np.array([[0,0,0]]))

            pointcloud.paint_uniform_color(POSE_COLOR['points'])

            for idx, smpl in enumerate(smpl_geometries):
                key = keys[idx]
                if 'pred' in key.lower():
                    if index >= 0:
                        smpl.vertices = o3d.utility.Vector3dVector(human_data[key][index])
                        # smpl.compute_vertex_normals()
                        smpl.paint_uniform_color(POSE_COLOR[key])
                    else:
                        smpl.vertices = o3d.utility.Vector3dVector(np.asarray(smpl.vertices) * 0)
                elif 'first' in key.lower():
                    smpl.vertices = o3d.utility.Vector3dVector(human_data[key][i])
                    # smpl.compute_vertex_normals()
                    smpl.paint_uniform_color(POSE_COLOR[key])
                    
                elif 'second' in key.lower():
                    smpl.vertices = o3d.utility.Vector3dVector(human_data[key][i])
                    # smpl.compute_vertex_normals()
                    smpl.paint_uniform_color(POSE_COLOR[key])

            if extrinsics is not None:
                # vis.set_view(view_list[i])
                if i > 0 and freeviewpoint:
                    camera_pose = self.get_camera()
                    # relative_pose = extrinsics[i] @ np.linalg.inv(extrinsics[i-1])
                    relative_trans = -extrinsics[i][:3, :3].T @ extrinsics[i][:3, 3] + extrinsics[i-1][:3, :3].T @ extrinsics[i-1][:3, 3]
                    
                    camera_positon = -(camera_pose[:3, :3].T @ camera_pose[:3, 3])
                    camera_pose[:3, 3] = -(camera_pose[:3, :3] @ (camera_positon + relative_trans))
                    self.init_camera(camera_pose)
                else:
                    self.init_camera(extrinsics[i])   
                    
            def add_first_cloud():
                self.add_geometry(pointcloud, reset_bounding_box = False, name='human points')  
                for si, smpl in enumerate(smpl_geometries):
                    self.add_geometry(smpl, reset_bounding_box = False, name=keys[si])  
                self.change_pause_status()

            if not init_param:
                init_param = True
                gui.Application.instance.post_to_main_thread(self.window, add_first_cloud)

            time.sleep(0.01)

            def updata_cloud():
                self.update_geometry(pointcloud,  name='human points') 
                for si, smpl in enumerate(smpl_geometries):
                    self.update_geometry(smpl, name=keys[si])  
                self.save_imgs(image_dir)
                self.waitKey(5, helps=False)
        
            gui.Application.instance.post_to_main_thread(
                self.window, updata_cloud)
                
        images_to_video(image_dir, video_name, delete=True)

        for g in smpl_geometries:
            self.remove_geometry(g)

    def add_geometry(self, geometry, name=None, mat=None, reset_bounding_box=True):
        if mat is None:
            mat =self.settings.material
        if name is None:
            name = self.scene_name
            
        geometry.transform(self.COOR_INIT)

        try: 
            if geometry.has_points():
                if not geometry.has_normals():
                    geometry.estimate_normals()
                geometry.normalize_normals()
        except:
            try:
                if len(geometry.triangles) == 0:
                    print(
                        "[WARNING] Contains 0 triangles, will read as point cloud")
                    geometry = None
                if not geometry.has_triangle_normals():
                    geometry.compute_vertex_normals()
                if len(geometry.vertex_colors) == 0:
                    geometry.paint_uniform_color([1, 1, 1])
                # Make sure the mesh has texture coordinates
                if not geometry.has_triangle_uvs():
                    uv = np.array([[0.0, 0.0]] * (3 * len(geometry.triangles)))
                    geometry.triangle_uvs = o3d.utility.Vector2dVector(uv)
            except:
                print("[Info]", "not PCD or pkl.")

        if name not in self.names:
            self.names.append(name)
        # print(name)
        self._scene.scene.add_geometry(name, geometry, mat)
        
        if reset_bounding_box:
            bounds = geometry.get_axis_aligned_bounding_box()
            self._scene.setup_camera(60, bounds, bounds.get_center())

    def update_geometry(self, geometry, name):
        self.remove_geometry(name)
        self.add_geometry(geometry, name, reset_bounding_box=False)

    def remove_geometry(self, name):
        self._scene.scene.remove_geometry(name)

    def set_view(self, view):
        pass
        # setup_camera(intrinsic_matrix, extrinsic_matrix, intrinsic_width_px, intrinsic_height_px): sets the camera view

    def get_camera(self):
        return np.eye(4)

    def init_camera(self, extrinsic_matrix, intrinsic_width_px=0, intrinsic_height_px=0): 
        pass

    def change_pause_status(self):
        pass

    def save_imgs(self, img_path):
        pass
        # self.export_image(img_path, 1080, 768)

    def waitKey(self, key=0, helps=False):
        while True:
            cv2.waitKey(key)
            if not o3dvis.PAUSE:
                break
    
def main():
    gui.Application.instance.initialize()

    w = o3dvis(1080, 720)

    gui.Application.instance.run()

if __name__ == "__main__":
    main()