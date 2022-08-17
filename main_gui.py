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
import sys
import cv2
import threading
import os
import time

sys.path.append('.')
sys.path.append('..')

from gui_vis import HUMAN_DATA, Setting_panal as base_gui, creat_plane
from util import load_scene as load_pts, images_to_video
from vis_smpl_scene import POSE_COLOR
from smpl import sample_path

class o3dvis(base_gui):
    # PAUSE = False
    IMG_COUNT = 0
    SCALE = 1.0

    def __init__(self, width=1280, height=768, is_remote=False):
        super(o3dvis, self).__init__(width, height)
        self.COOR_INIT = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
        self.intrinsic = np.array([[623.53829072,   0.        , 639.5       ],
                                    [  0.        , 623.53829072, 359.5       ],
                                    [  0.        ,   0.        ,   1.        ]])
        self.scene_name = 'ramdon'
        self.Human_data = HUMAN_DATA(is_remote)
        self.is_done = False
        self.data_names = {}
        for i, plane in enumerate(creat_plane()):
            self.add_geometry(plane, name=f'ground_{i}')

    def load_scene(self, scene_path):
        self.window.close_dialog()
        if not os.path.isfile(scene_path):
            return
        self.scene_name = os.path.basename(scene_path).split('.')[0]
        # self._on_load_dialog_done(scene_path)
        load_pts(self, scene_path)

    def _on_load_smpl_done(self, filename):
        self.window.close_dialog()
        self.Human_data.load(filename) 

        if self.Human_data:
            threading.Thread(target=self.update_thread).start()

    def reset_settings(self):
        o3dvis.IMG_COUNT = 0
        # o3dvis.FREE_VIEW = False
        # o3dvis.PAUSE = False
        # o3dvis.POV = 'first'
        # o3dvis.RENDER = False
        # self._set_slider_value(0)

    def update_thread(self):
        """
        The function is to render the 3D point cloud and the SMPL mesh in the same window
        """
        vis_data = self.Human_data.vis_data_list

        video_name = self.scene_name

        pointcloud = o3d.geometry.PointCloud()
        smpl_geometries = []
        human_data = vis_data['humans']
        points = vis_data['point cloud'][0]
        indexes = vis_data['point cloud'][1]

        for i in human_data:
            smpl = o3d.io.read_triangle_mesh(sample_path)
            smpl.vertex_colors = o3d.utility.Vector3dVector()
            smpl_geometries.append(smpl) # a ramdon SMPL mesh
    
        keys = list(human_data.keys())
        init_param = False

        total_frames = human_data[keys[0]].shape[0]

        self._set_slider_limit(0, total_frames)

        while True:
            video_name += time.strftime("-%Y-%m-%d_%H-%M", time.localtime())
            image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'temp_{video_name}')
            self.reset_settings()
            while self._get_slider_value() < total_frames:
            # for i in range(total_frames):
                i = self._get_slider_value()
                self._set_slider_value(i+1)
                
                _, extrinsics = self.Human_data.get_cameras(o3dvis.POV)

                time.sleep(0.1)
                if i in indexes:
                    index = indexes.index(i)
                    pointcloud.points = o3d.utility.Vector3dVector(points[index])
                else:
                    index = -1
                    pointcloud.points = o3d.utility.Vector3dVector(np.array([[0,0,0]]))

                pointcloud.normals = o3d.utility.Vector3dVector()
                pointcloud.paint_uniform_color(POSE_COLOR['points'])

                for idx, smpl in enumerate(smpl_geometries):
                    # smpl = o3d.geometry.TriangleMesh()
                    key = keys[idx]
                    if 'pred' in key.lower():
                        if index >= 0:
                            smpl.vertices = o3d.utility.Vector3dVector(human_data[key][index])
                            smpl.vertex_normals = o3d.utility.Vector3dVector()
                            smpl.triangle_normals = o3d.utility.Vector3dVector()
                            smpl.compute_vertex_normals()
                            if len(smpl.vertex_colors) == 0:
                                smpl.paint_uniform_color(POSE_COLOR[key])
                        else:
                            smpl.vertices = o3d.utility.Vector3dVector(np.zeros((6890, 3)))
                    elif 'first' in key.lower() or 'second' in key.lower():
                        smpl.vertices = o3d.utility.Vector3dVector(human_data[key][i])
                        smpl.vertex_normals = o3d.utility.Vector3dVector()
                        smpl.triangle_normals = o3d.utility.Vector3dVector()
                        smpl.compute_vertex_normals()
                        if len(smpl.vertex_colors) == 0:
                            smpl.paint_uniform_color(POSE_COLOR[key])
                    else :
                        print('Edit your key in human_data here!')

                if extrinsics is not None:
                    # vis.set_view(view_list[i])
                    if i > 0 and o3dvis.FREE_VIEW:
                        camera_pose = self.get_camera()
                        relative_trans = -extrinsics[i][:3, :3].T @ extrinsics[i][:3, 3] + extrinsics[i-1][:3, :3].T @ extrinsics[i-1][:3, 3]
                        
                        relative_trans = self.COOR_INIT[:3, :3] @ relative_trans

                        camera_positon = -(camera_pose[:3, :3].T @ camera_pose[:3, 3])
                        camera_pose[:3, 3] = -(camera_pose[:3, :3] @ (camera_positon + relative_trans))
                        self.init_camera(camera_pose)
                    else:
                        self.init_camera(extrinsics[i] @ self.COOR_INIT)   
                        
                def add_first_cloud():
                    self.add_geometry(pointcloud, reset_bounding_box = False, name='human points')  
                    for si, smpl in enumerate(smpl_geometries):
                        self.add_geometry(smpl, reset_bounding_box = False, name=keys[si])  
                    self.change_pause_status()

                def updata_cloud():
                    self.update_geometry(pointcloud,  name='human points') 
                    for si, smpl in enumerate(smpl_geometries):
                        self.update_geometry(smpl, name=keys[si])  
                    if o3dvis.RENDER:
                        self.save_imgs(image_dir)

                if not init_param:
                    init_param = True
                    gui.Application.instance.post_to_main_thread(self.window, add_first_cloud)
                else:
                    gui.Application.instance.post_to_main_thread(self.window, updata_cloud)

                self.waitKey(5, helps=False)
                    
            images_to_video(image_dir, video_name, delete=True)

        # for g in smpl_geometries:
        #     self.remove_geometry(g)

    def add_geometry(self, geometry, name=None, mat=None, reset_bounding_box=True):
        if mat is None:
            mat =self.settings.material
        if name is None:
            name = self.scene_name

        try: 
            if geometry.has_points():
                if not geometry.has_normals():
                    geometry.estimate_normals()
                geometry.normalize_normals()
                # geometry.orient_normals_towards_camera_location(np.array([0, 5, 5]))
        except:
            try:
                if not geometry.has_triangle_normals():
                    geometry.compute_vertex_normals()
                if len(geometry.vertex_colors) == 0:
                    geometry.paint_uniform_color([1, 1, 1])
                # Make sure the mesh has texture coordinates
                if not geometry.has_triangle_uvs():
                    uv = np.array([[0.0, 0.0]] * (3 * len(geometry.triangles)))
                    geometry.triangle_uvs = o3d.utility.Vector2dVector(uv)

                # self_intersecting = geometry.is_self_intersecting()
                # watertight = geometry.is_watertight()
            except:
                print("[Info]", "not pointcloud or mehs.")

        geometry.rotate(self.COOR_INIT[:3, :3], self.COOR_INIT[:3, 3])
        geometry.scale(o3dvis.SCALE, (0.0, 0.0, 0.0))

        if name not in self.data_names.keys():
            box = gui.Checkbox(name)
            box.set_on_checked(self._on_show_geometry)
            box.checked = True
            self.check_boxes.add_child(box)
            self.data_names[name] = box

        elif self._scene.scene.has_geometry(name):
            self._scene.scene.remove_geometry(name)

        if self.data_names[name].checked:
            self._scene.scene.add_geometry(name, geometry, mat)
        
        if reset_bounding_box:
            try:
                bounds = geometry.get_axis_aligned_bounding_box()
                self._scene.setup_camera(60, bounds, bounds.get_center())
            except:
                print("[WARNING] It is t.geometry type")

    def _on_show_geometry(self, show):
        for name, box in self.data_names.items():
            self._scene.scene.show_geometry(name, box.checked)
        # self._apply_settings()

    def update_geometry(self, geometry, name):
        # self.remove_geometry(name)
        self.add_geometry(geometry, name, reset_bounding_box=False)

    def remove_geometry(self, name):
        self._scene.scene.remove_geometry(name)

    def set_view(self, view):
        pass

    def get_camera(self):
        view = self._scene.scene.camera.get_view_matrix()
        view[1, :] = - view[1, :]
        view[2, :] = - view[2, :]
        view[:3, 3] /= o3dvis.SCALE 
        return view

    def init_camera(self, extrinsic_matrix): 
        bounds = self._scene.scene.bounding_box
        extrinsic_matrix[:3, 3] *= o3dvis.SCALE 
        self._scene.setup_camera(self.intrinsic, extrinsic_matrix, 1280, 720, bounds)

    def save_imgs(self, img_dir):
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)
        frame = self._scene.frame
        img_path = os.path.join(img_dir, f'{o3dvis.IMG_COUNT:04d}.jpg')
        o3dvis.IMG_COUNT += 1
        self.export_image(img_path, 1280, 720)

    def waitKey(self, key=0, helps=False):
        while o3dvis.PAUSE:
            cv2.waitKey(key)
            pass
    
def main():
    gui.Application.instance.initialize()

    w = o3dvis(1280, 720)

    gui.Application.instance.run()

if __name__ == "__main__":
    main()