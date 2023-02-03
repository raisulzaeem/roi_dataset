import argparse
import json
import os
import shutil
from tqdm import tqdm


if __name__=="__main__":

    parser = argparse.ArgumentParser(description="Arguments to prepare the dataset")
    parser.add_argument('-i','--image_dir', default="C:\\Users\\rislam\\Documents\\Python Scripts\\ROI\\images\\latest_roi_repro", required=False)


    args = parser.parse_args()
    image_dir = args.image_dir

    with open('last_scan.json') as f:
        last_scan = json.load(f)

    roi_count = last_scan['roi_count']
    
    with open(f'images_and_roi{roi_count}.json') as f:
        images_and_annotation = json.load(f)

    count = 0
    pbar = tqdm(total=len(images_and_annotation.keys()))

    for source_image_path in images_and_annotation.keys():
        dest_image_path = os.path.join(image_dir,os.path.basename(source_image_path))
        if not os.path.exists(dest_image_path):
            if not os.path.exists(source_image_path):
                if source_image_path.endswith('.jpg'):
                    source_image_path = source_image_path.replace('.jpg','.jpeg')
                elif source_image_path.endswith('.jpeg'):
                    source_image_path = source_image_path.replace('.jpeg','.jpg')
                if not os.path.exists(source_image_path):
                    continue
            
            shutil.copy(source_image_path, dest_image_path)
        count+=1
        pbar.update()
        # print(count)

    print("!")


