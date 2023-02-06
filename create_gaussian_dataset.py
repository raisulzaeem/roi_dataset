import cv2 as cv
import json
import os
import numpy as np

image_dir = "/roi/latest_roi_repro" #"C:\\Users\\rislam\\Documents\\Python Scripts\\ROI\\images\\latest_roi_repro"
gaussian_dir = "/roi/latest_roi_repro_gaussian_2048" #"C:\\Users\\rislam\\Documents\\Python Scripts\\ROI\\images\\gaussian_2048"


point_per_inch = 300
inch_to_mm = 25.4
point_to_mm = inch_to_mm/point_per_inch
mm_to_pixel = point_per_inch/ inch_to_mm

# with open("images_and_roi10100.json") as f:
#     images_and_roi = json.load(f) # in mm



def create_gaussian_image(image_path, xywh, output_dir, dimension=512):
    x,y,w,h = [int(i*dimension) for i in xywh]
    black = np.zeros((dimension, dimension), dtype= np.uint8)
    if (x+w>=(dimension-1)):
        w = dimension-x-2
    if (y+h>=(dimension-1)):
        h = dimension-y-2
    black[y:y+h+1,x:x+w+1] = 255
    black[y+1:y+h,x+1:x+w] = 0
    black = cv.GaussianBlur(black, (5,5),1)
    black = ((black.astype(np.float16)/black.max())*255).astype(np.uint8)

    cv.imwrite(os.path.join(output_dir, os.path.basename(image_path)), black)

if __name__ == "__main__":

    with open('last_scan.json') as f:
        last_scan = json.load(f)

    roi_count = last_scan['roi_count']

    with open(f'images_and_roi{roi_count}.json') as f:
        images_and_roi_mm = json.load(f)

    if os.path.exists("images_roi_percent_latest.json"):
        with open("images_roi_percent_latest.json") as f:
            local_images_roi_percentage_dict = json.load(f)
    else:
        local_images_roi_percentage_dict = {}

    local_images_roi_percentage_dict_keys = local_images_roi_percentage_dict.keys()

    if not os.path.exists(gaussian_dir):
        os.makedirs(gaussian_dir)

    for image_path, roi_mm in images_and_roi_mm.items():
        local_image_path = os.path.join(image_dir, os.path.basename(image_path))
        if not os.path.exists(local_image_path):
            continue
        if local_image_path in local_images_roi_percentage_dict_keys:
            continue
        try:
            image = cv.imread(local_image_path,-1)
            image_height, image_width, _ = image.shape
            roi_pixel = [roi*mm_to_pixel for roi in roi_mm]
            roi_in_percent = [roi_pixel[0]/image_width, roi_pixel[1]/image_height, roi_pixel[2]/image_width, roi_pixel[3]/image_height]
            create_gaussian_image(local_image_path,roi_in_percent, gaussian_dir, dimension=2048)
            local_images_roi_percentage_dict.update({local_image_path:roi_in_percent})
        except Exception as e:
            print("Error : ",e.__class__)

        with open("images_roi_percent_latest.json",'w') as f:
            json.dump(local_images_roi_percentage_dict,f)

    







