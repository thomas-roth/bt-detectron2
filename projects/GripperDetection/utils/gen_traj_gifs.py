import os
from PIL import Image
from natsort import natsorted

from tqdm import tqdm


SOURCE = "/home/temp_store/troth/outputs/gripper_detection/eval"
DEST = "/home/temp_store/troth/outputs/gripper_detection/eval/traj_gifs"

NUM_SEQUENCES = 242


for root_eval, dirs_seq, _ in os.walk(SOURCE):
    dirs_seq = natsorted(dirs_seq)
    for dir_seq in tqdm(dirs_seq, total=NUM_SEQUENCES):
        imgs_cam_1 = []
        imgs_cam_2 = []

        for root_seq, _, files_img in os.walk(os.path.join(root_eval, dir_seq, "trajs")):
            files_img = natsorted(files_img)
            for file_img in files_img:
                assert file_img.endswith(".jpg")

                if "cam_1" in file_img:
                    imgs_cam_1.append(os.path.join(root_seq, file_img))
                elif "cam_2" in file_img:
                    imgs_cam_2.append(os.path.join(root_seq, file_img))

        gif_frames_cam_1 = [Image.open(img).quantize(colors=256, method=2, kmeans=1) for img in imgs_cam_1]
        gif_frames_cam_2 = [Image.open(img).quantize(colors=256, method=2, kmeans=1) for img in imgs_cam_2]

        os.makedirs(os.path.join(DEST), exist_ok=True)
        gif_frames_cam_1[0].save(os.path.join(DEST, f"{dir_seq}_cam_1.gif"), save_all=True, append_images=gif_frames_cam_1[1:], duration=200, loop=0)
        gif_frames_cam_2[0].save(os.path.join(DEST, f"{dir_seq}_cam_2.gif"), save_all=True, append_images=gif_frames_cam_2[1:], duration=200, loop=0)