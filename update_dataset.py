import cv2 as cv
import json
import numpy as np
import os
import requests
import shutil
from tqdm import tqdm
import xml.etree.ElementTree as ET


point_per_inch = 300
inch_to_mm = 25.4
point_to_mm = inch_to_mm/point_per_inch
mm_to_pixel = point_per_inch/ inch_to_mm


def read_mediagate_info(mediagate_id):
    request_url = 'https://api.saueressig.de/MediagateAPI/MediagateDetails'
    information = {'ids' : [mediagate_id]}
    search_response = requests.post(request_url, json = information, auth = ('web2gravure', '5#dlKjgjAwh!!'))
    return search_response.json()['Result'][0]


def get_xml_path(image_path):
    """Filenames under the json_file["IMAGE_PATH"] is not always correct.
    This method deals with this issue. The possible deviations are:
    
    Möglichkeit_1:  
    json_file["IMAGE_PATH"] = xyz.jpg
    Im Ornder = xyz.jpeg, xyz.xml

    Möglichkeit_2:
    json_file["IMAGE_PATH"] = xyz.jpg
    Im Ornder = xyz_1.jpeg, xyz.xml, xyz_2.jpeg
    
    Möglichkeit_3: 
    json_file["IMAGE_PATH"] = xyz.a.jpg
    Im Ornder = xyz_a.jpeg, xyz_a.xml, ....        

    Möglichkeit_4: 
    json_file["IMAGE_PATH"] = xyz.a.jpg
    Im Ornder = xyz_a_1.jpeg, xyz_a_2.jpeg, xyz_a.xml, ...."""

    xml_path = "Life is too short to take stress"
    if image_path.endswith('.jpg'):
        xml_path = image_path.replace('.jpg','.xml')
    if image_path.endswith('.jpeg'):
        xml_path = image_path.replace('.jpeg','.xml')
    if not os.path.exists(xml_path):
        xml_path = '_'.join(image_path.split('.')[:-1])+'.xml'
    if not os.path.exists(xml_path):
        print('--------------------------\n',xml_path, " doesn't exist \n")
        print("Life is boring, take some stress. \n\nBy the way, No xml file found\n")
        xml_path = None
    return xml_path


def get_encoway_wh(mediagate_id):
    mediagate_info = read_mediagate_info(str(mediagate_id))
    if not mediagate_info['ENC_EBREITE'] or not mediagate_info['ENC_EHOEHE']:
        return 0,0
    enc_wh = np.array([float(mediagate_info['ENC_EBREITE']),float(mediagate_info['ENC_EHOEHE'])])
    return enc_wh

def get_roi(xml_path): # in mm
    point_per_inch = 72
    point_to_mm = inch_to_mm/point_per_inch
    if not os.path.exists(xml_path):
        return 0,0,0,0
    tree = ET.parse(xml_path)
    root = tree.getroot() 
    pageboxes_element = root.find("pageboxes")
    media_element = pageboxes_element.find("media")
    trim_element = pageboxes_element.find("trim")

    try:
        media_offsetx = float(media_element.find("offsetx").text)
        media_offsety = float(media_element.find("offsety").text)
        media_height = float(media_element.find("height").text)

        trim_offsetx = float(trim_element.find("offsetx").text)
        trim_offsety = float(trim_element.find("offsety").text)

        roi_height = float(trim_element.find("height").text) * point_to_mm
        roi_width = float(trim_element.find("width").text) * point_to_mm
    except Exception as e:
        print("Error!", e.__class__, "occurred.")
        return 0,0,0,0


    # our local (0,0) at bottom left corner, opencv hat (0,0) on top left corner. 
    roi_y_bottom_left = (trim_offsety -media_offsety)
    roi_y = (media_height - roi_y_bottom_left) * point_to_mm
    roi_y = roi_y-roi_height
    roi_x = (trim_offsetx - media_offsetx) * point_to_mm

    return roi_x, roi_y, roi_width, roi_height
    

def check_dimension(dimension_1, dimension_2, tolerance=0.02):

    d1_max = np.max(dimension_1)
    d2_max = np.max(dimension_2)
    diff_max = abs((d1_max-d2_max)/d2_max)

    d1_min = np.min(dimension_1)
    d2_min = np.min(dimension_2)
    diff_min = abs((d1_min-d2_min)/d2_min)

    if ((diff_max<tolerance) and (diff_min<tolerance)):
        return True
    else:
        return False


def mediagate_id_to_image_path(mediagate_id):
    """From the .json file, get the image path and the corresponding directory(where also .xml file and the separation directory are available)  
    
    Example:
        with mediagate_id = 1061278:

            http://devwebvm087.saueressig.de/mediagate/public/clynx/fileinfo?id=1061278

        .json file:    
            {
                "ENC_DRUCKVERFAHREN":null,"ENC_JOBTYP":null,
                "ENC_DRUCKART":null,
                "IMAGE_PATH":"/210611/210611_001/210611_001_007/210611_001_007_pdf/210611_001_007tri_eyec.jpg",
                "FILE_TYPE":"daily",
                "IMAGE_URL":"http://devwebvm087.saueressig.de/mediagate/public/clynx/lowres?id=1061278",
                "STATUS":1,"MESSAGE":""    
            }
    """
    url = 'http://devwebvm087.saueressig.de/mediagate/public/clynx/fileinfo?id=' + str(mediagate_id)

    response = requests.get(url)
    json_content = response.json()
    image_path = json_content['IMAGE_PATH']
    # lowres_url = json_content['IMAGE_URL']

 

    if json_content['FILE_TYPE'] == 'daily':
        return None
        # image_path = '//devarcsv041/orderdata/customer_files/' + image_path
    else:
        image_path = '//devarcsv041/orderdata/repro_files/' + image_path

    if os.name == 'posix':
        image_path = image_path.replace('//devarcsv041','/Netz/devarcsv041')

    return image_path


def roi_annotation(mediagate_id, tolerance = 0.02):
    """For the given mediagate id compares the width height from the encoway with xml. Returns the x,y,w,h in mm if the deviation is within tolerance.

    Args:
        mediagate_id : mediagate_id.
        tolerance    : tolerance. 

    Returns:
        dict(image_path : [x,y,w,h]) if the deviation is within tolerance; None otherwise
    """
    point_per_inch = 72
    mm_to_inch = 1/25.4
    mm_to_pixel = mm_to_inch * point_per_inch
    enc_wh = get_encoway_wh(mediagate_id)
    image_path = mediagate_id_to_image_path(mediagate_id)
    if image_path is None:
        return None
    xml_path = get_xml_path(image_path)

    if xml_path is None:
        return None
    x,y,w,h = get_roi(xml_path) # in mm
    wh = np.array([w,h])

    splits = image_path.split('.')
    image_path_raw = splits[0]+'_RAW.'+splits[1]
    if check_dimension(wh , enc_wh, tolerance=tolerance):
        return {image_path_raw : [x,y,w,h]}
    else:
        return None


def fetch_images(roi_count, image_dir):
    """Reads the paths from 'images_and_roi{roi_count}.json' and copies each image in image dir.

    Args:
        roi_count : last roi count, floored to 100s. i.e. for 1870, it will be 1800.
        image_dir : directory, where the images will be copied. 

    Returns:
        None
    """

    if not os.path.exists(image_dir):
        os.makedirs(image_dir)
    
    with open(f'images_and_roi{roi_count}.json') as f:
        images_and_annotation = json.load(f)


    for source_image_path in tqdm(images_and_annotation.keys()):
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


def resize_and_write_image(image_path, output_dir, dimension=2048):
    """Reads an image from path, resizes the image according to the given dimension and saves it to the output_dir.

    Args:
        image_path : path to the image.
        output_dir : directory, where the images will be saved.
        dimension  : dimension, to which image will be resized 

    Returns:
        Bool : True is successfull, False otherwise
    """
    dest_path = os.path.join(output_dir, os.path.basename(image_path))
    try:
        if os.path.exists(dest_path):
            return True
        image = cv.imread(image_path, cv.IMREAD_COLOR)
        reduced_image = cv.resize(image, (dimension,dimension))
        cv.imwrite(dest_path,reduced_image)
        return True
    except Exception as e:
        print(e.__class__)
        return False


def create_gaussian_image(image_path, xywh, output_dir, dimension=2048):
    """Creates a numpy array in the shape of (dimension x dimension) with zeros.
    The rectangle corresponding region of interest has 255. We apply gaussian blur, because the in the real image
    the lines represent gaussian distribution. Normalize the blurred image so that maximum is 255.

    Args:
        image_path : uses this path just to save the image with this name, doesn't read the original image.
        xywh : A list with [x,y,w,h]; the dimensions are in pixels.
        output_dir : Directory to save the gaussian array/images.
        dimension : The size of the array/image 

    Returns:
        None
    """
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

def update_roi_latest(start_mediagate_id, start_roi):
    
    if os.path.exists(f'images_and_roi{start_roi}.json'):
        with open(f'images_and_roi{start_roi}.json') as f:
            images_and_annotation = json.load(f)
    else:
        images_and_annotation = {}

    error_count = 0
    roi_count_it = start_roi
    roi_count = start_roi
    mediagate_id = start_mediagate_id

    while True:
        mediagate_id += 1
        # print(f"Start Mediagate_id : {mediagate_id} \n Roi Count : {roi_count_it}") # DEBUG
        try:
            annotation = roi_annotation(mediagate_id)
            if annotation is None:
                continue
            roi_count_it+=1
            print(annotation)
            images_and_annotation.update(annotation)
            
            error_count = 0
            if roi_count_it%100==0:
                roi_count = roi_count_it
                with open(f"images_and_roi{roi_count}.json",'w') as f:
                    json.dump(images_and_annotation, f)
                with open('last_scan.json','w') as f:
                    json.dump({'last_mediagate_id':mediagate_id,'roi_count':roi_count}, f)
        except Exception as e:
            print("Error!", e.__class__, "occurred.")
            error_count+=1
        
        if error_count>100:
            break
        
    return mediagate_id, roi_count

def resized_and_gaussian_images(roi_count, image_dir, image_dir_dim, gaussian_dir):
    with open(f'images_and_roi{roi_count}.json') as f:
        images_and_roi_mm = json.load(f)

    if os.path.exists("images_roi_percent_latest.json"):
        with open("images_roi_percent_latest.json") as f:
            local_images_roi_percentage_dict = json.load(f)
    else:
        local_images_roi_percentage_dict = {}

    if not os.path.exists(gaussian_dir):
        os.makedirs(gaussian_dir)

    if not os.path.exists(image_dir_dim):
        os.makedirs(image_dir_dim)
    

    for image_path, roi_mm in tqdm(images_and_roi_mm.items()):
        local_image_path = os.path.join(image_dir, os.path.basename(image_path))
        if not os.path.exists(local_image_path):
            continue
        if local_image_path in local_images_roi_percentage_dict:
            if (os.path.exists(os.path.join(image_dir_dim, os.path.basename(local_image_path))) and os.path.exists(os.path.join(gaussian_dir, os.path.basename(local_image_path)))):
                continue
        try:
            image = cv.imread(local_image_path,-1)
            image_height, image_width, _ = image.shape
            roi_pixel = [roi*mm_to_pixel for roi in roi_mm]
            roi_in_percent = [roi_pixel[0]/image_width, roi_pixel[1]/image_height, roi_pixel[2]/image_width, roi_pixel[3]/image_height]
            if not resize_and_write_image(local_image_path, image_dir_dim, dimension):
                if local_image_path in local_images_roi_percentage_dict:
                    local_images_roi_percentage_dict.pop(local_image_path, None)
                continue
            create_gaussian_image(local_image_path,roi_in_percent, gaussian_dir, dimension)

            local_images_roi_percentage_dict.update({local_image_path:roi_in_percent})
        except Exception as e:
            print("Error : ",e.__class__)
            if local_image_path in local_images_roi_percentage_dict:
                local_images_roi_percentage_dict.pop(local_image_path, None)

        with open("images_roi_percent_latest.json",'w') as f:
            json.dump(local_images_roi_percentage_dict,f)

if __name__ == "__main__":

    """
    Requirements:
            1.'//devarcsv041/orderdata/repro_files/' is connected to the container/system
            2. Has access to company network (for different http calls)

    Input : 
            1. last_scan.json
            2. images_and_roi{roi_count}.json
            3. image directory
            4. image directory for reduced images
            5. image directory for gaussian images

    Output / Actions :
            1. last_scan.json -> updated after every 100 roi count
            2. images_and_roi{roi_count}.json -> updated after every 100 roi count
            3. images copied from the server to image directory
            4. resizes image and saves to the reduced image directory
            5. writes gaussian image in the given dimension
            

    """

    if os.path.exists('last_scan.json'):
        with open('last_scan.json') as f:
            last_scan = json.load(f)    
        mediagate_id = last_scan['last_mediagate_id'] # start mediagate id {"last_mediagate_id": 1268138, "roi_count": 10100}
        roi_count = last_scan['roi_count']
    else:
        mediagate_id = 1218610 # First mediagate id from 15.08.2022
        roi_count = 0
    
    
    image_dir = "/roi/latest_roi_repro" #"C:\\Users\\rislam\\Documents\\Python Scripts\\ROI\\images\\latest_roi_repro"
    dimension = 2048
    image_dir_dim = f"/roi/latest_roi_repro_{dimension}"
    gaussian_dir = f"/roi/latest_roi_repro_gaussian_{dimension}" #"C:\\Users\\rislam\\Documents\\Python Scripts\\ROI\\images\\gaussian_2048"

    # xxxxx  --------- Update Json -------- xxxxx #

    print("Function : update_roi_latest")
    mediagate_id, roi_count = update_roi_latest(mediagate_id, roi_count)

    # xxxxx  --------- FETCH IMAGES -------- xxxxx #
    print("Function : fetch_images")
    fetch_images(roi_count, "/roi/latest_roi_repro")

    # xxxxx --------- Write images with reduced size and gaussian images -------- #
    print("Function : resized_and_gaussian_images")
    resized_and_gaussian_images(roi_count, image_dir, image_dir_dim, gaussian_dir)

    print("DONE!")






