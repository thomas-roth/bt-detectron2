import cv2
import torch
from tqdm import tqdm

from detectron2.config.config import get_cfg
from detectron2.data.catalog import MetadataCatalog
from detectron2.data.datasets.irl_kitchen_gripper_detection import register_all_irl_kitchen_gripper_detection
from detectron2.engine.defaults import DefaultTrainer, default_argument_parser, default_setup
from detectron2.modeling import build_model
from detectron2.checkpoint import DetectionCheckpointer
from detectron2.utils.visualizer import Visualizer
from projects.GripperDetection.build_trajs import build_trajectory


MODEL_PATH = "/home/temp_store/troth/outputs/gripper_detection/models/2025_01_05-19_47_58/model_final.pth"


# wrapper to squeeze items from dataset to fit model input shape
class GripperDetectionDatasetWrapper(torch.utils.data.Dataset):
    def __init__(self, dataset):
        self.dataset = dataset

    def __len__(self):
        return len(self.dataset)
    
    def __getitem__(self, idx):
        item = self.dataset[idx]
        return item


def setup_cfg(args):
    """
    Create configs and perform basic setups.
    """

    cfg = get_cfg()
    cfg.merge_from_file("/home/i53/student/troth/code/bt/detectron2/projects/GripperDetection/configs/gripper_detection.yaml")
    cfg.ROBOT_STATE_ANNOTATIONS_PATH = "/home/temp_store/troth/data/irl_kitchen_gripper_detection/robot_state_annotations/"
    cfg.freeze()
    default_setup(cfg, args)

    return cfg


def _merge_instances(instances):
    # merge instances of gripper bboxes to biggest bbox

    x_mins = instances.pred_boxes.tensor[:, 0]
    y_mins = instances.pred_boxes.tensor[:, 1]
    x_maxs = instances.pred_boxes.tensor[:, 2]
    y_maxs = instances.pred_boxes.tensor[:, 3]

    instances.pred_boxes.tensor = torch.stack([x_mins.min(), y_mins.min(), x_maxs.max(), y_maxs.max()]).unsqueeze(0)

    instances.pred_classes = torch.tensor([0]) # only one class

    # calculate new score as weighted average of scores of merged bboxes (weight is size percentage of merged bbox)
    bbox_weights = (x_maxs - x_mins) * (y_maxs - y_mins) / ((x_maxs.max() - x_mins.min()) * (y_maxs.max() - y_mins.min()))
    instances.scores = (bbox_weights * instances.scores).sum().unsqueeze(0) / bbox_weights.sum()

    return instances


def main(args, visualize_output=True, build_trajs=True, only_build_first_traj=False):
    cfg = setup_cfg(args)

    model = build_model(cfg)
    DetectionCheckpointer(model).load(MODEL_PATH)

    model.eval()

    register_all_irl_kitchen_gripper_detection()

    test_data_loader = DefaultTrainer.build_test_loader(cfg, "irl_kitchen_gripper_detection_cam_1_seq_000")
    test_data_loader = GripperDetectionDatasetWrapper(test_data_loader.dataset)

    with torch.no_grad():
        outputs = model(test_data_loader)

    if visualize_output:
        for i, (input, output) in tqdm(enumerate(zip(test_data_loader, outputs)), total=len(test_data_loader), desc="Visualizing images"):
            if len(output["instances"].pred_boxes.tensor) == 0:
                continue # skip frame if no gripper detected

            output["instances"] = _merge_instances(output["instances"])

            input_img = cv2.imread(input["file_name"])
            visualizer = Visualizer(input_img[:, :, ::-1], MetadataCatalog.get(cfg.DATASETS.TRAIN[0]), scale=1.0)
            input_img_with_bboxes = visualizer.draw_instance_predictions(output["instances"].to("cpu"))
            cv2.imwrite(cfg.OUTPUT_DIR + f"/eval/bboxes/{input['image_id']}_bbox_{i:02d}.jpg", input_img_with_bboxes.get_image()[:, :, ::-1])
    
    if build_trajs:
        for i, input in tqdm(enumerate(test_data_loader), total=1 if only_build_first_traj else len(test_data_loader), desc="Building trajectories"):
                input_img = cv2.imread(input["file_name"])
                anno_file_path = cfg.ROBOT_STATE_ANNOTATIONS_PATH + f"/{str.join('_', str(input['image_id']).split('_')[:-4])}.pickle" # remove cam & img nr from image_id
                img_with_trajectory = build_trajectory(input_img, outputs, anno_file_path=anno_file_path, start_index=i)
                
                cv2.imwrite(cfg.OUTPUT_DIR + f"/eval/trajs/{input['image_id']}_traj_{i:02d}.jpg", img_with_trajectory)
                
                if only_build_first_traj:
                    break


if __name__ == "__main__":
    args = default_argument_parser().parse_args()
    main(args, visualize_output=False, build_trajs=True, only_build_first_traj=False)
