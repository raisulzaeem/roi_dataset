import requests
import numpy as np
import os
import xml.etree.ElementTree as ET
import json


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
    ich_to_mm = 25.4
    point_to_mm = ich_to_mm/point_per_inch
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


def roi_annotation(mediagate_id):
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
    if check_dimension(wh , enc_wh):
        return {image_path_raw : [x,y,w,h]}
    else:
        return None


if __name__ == "__main__":

    with open('last_scan.json') as f:
        last_scan = json.load(f)
    
    mediagate_id = last_scan['last_mediagate_id'] # start mediagate id {"last_mediagate_id": 1268138, "roi_count": 10100}
    roi_count = last_scan['roi_count']
    error_count = 0

    with open(f'images_and_roi{roi_count}.json') as f:
        images_and_annotation = json.load(f)

    while True:
        mediagate_id += 1
        try:
            annotation = roi_annotation(mediagate_id)
            if annotation is None:
                continue
            roi_count+=1
            print(annotation)
            images_and_annotation.update(annotation)
            
            error_count = 0
            if roi_count%100==0:
                with open(f"images_and_roi{roi_count}.json",'w') as f:
                    json.dump(images_and_annotation, f)
                with open('last_scan.json','w') as f:
                    json.dump({'last_mediagate_id':mediagate_id,'roi_count':roi_count}, f)
        except Exception as e:
            print("Error!", e.__class__, "occurred.")
            error_count+=1
        
        if error_count>100:
            break
    
    os.system("python fetch_images.py")

