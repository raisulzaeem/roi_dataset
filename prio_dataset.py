import csv
import cv2 as cv
import json
import os
import numpy as np
import pandas as pd
import requests
import xml.etree.ElementTree as ET

def csv_to_list(csv_path):
    with open(csv_path) as f:
        reader_data = csv.reader(f)
        list_data = list(reader_data)
    
    return list_data


def read_mediagate_info(mediagate_id):
    request_url = 'https://api.saueressig.de/MediagateAPI/MediagateDetails'
    information = {'ids' : [mediagate_id]}
    search_response = requests.post(request_url, json = information, auth = ('web2gravure', '5#dlKjgjAwh!!'))
    return search_response.json()['Result'][0]



def get_encoway_wh(mediagate_id):
    mediagate_info = read_mediagate_info(str(mediagate_id))
    if not mediagate_info['ENC_EBREITE'] or not mediagate_info['ENC_EHOEHE']:
        return 0,0
    enc_wh = np.array([float(mediagate_info['ENC_EBREITE']),float(mediagate_info['ENC_EHOEHE'])])
    return enc_wh


def mediagate_2_image_path(mediagate_id, server_path):
    response = requests.get(f"http://devwebvm087.saueressig.de/mediagate/public/clynx/fileinfo?id={mediagate_id}")
    response_dict = response.json()
    if response_dict["FILE_TYPE"] == "daily":
        image_path = os.path.join(server_path, "customer_files", *response_dict["IMAGE_PATH"].split('/'))
    else:
        image_path = os.path.join(server_path, "repro_files", *response_dict["IMAGE_PATH"].split('/'))
    
    image_path = image_path.replace('.jpg','.jpeg')
    
    if os.path.exists(image_path):
        return image_path
    else:
        image_path_1 = image_path.replace('.jpeg','_1.jpeg')
        if os.path.exists(image_path_1):
            return image_path_1
        print(f"Couldn't find {image_path}")
        return None  


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
    if image_path.endswith('_1.jpeg'):
        xml_path = image_path.replace('_1.jpeg','.xml')
    elif image_path.endswith('.jpeg'):
        xml_path = image_path.replace('.jpeg','.xml')
    if not os.path.exists(xml_path):
        xml_path = '_'.join(image_path.split('.')[:-1])+'.xml'
    if not os.path.exists(xml_path):
        print('--------------------------\n',xml_path, " doesn't exist \n")
        print("Life is boring, take some stress. \n\nBy the way, No xml file found\n")
        xml_path = None
    return xml_path


def get_roi(xml_path):

    # Die Einheit der PageBoxen und Offset in der XML sind „Points“, also 1/72 inch (25,4cm=10inch=720pints)
    # Die JPEGS sind mit 300DPI erstellt
    point_per_inch = 1/72
    pixel_per_inch = 300
    point_to_pixel = point_per_inch*pixel_per_inch


    if not os.path.exists(xml_path):
        return 0,0,0,0
    tree = ET.parse(xml_path)
    root = tree.getroot() 
    pageboxes_element = root.find("pageboxes")
    media_element = pageboxes_element.find("media")
    trim_element = pageboxes_element.find("trim")

    media_offsetx = float(media_element.find("offsetx").text)
    media_offsety = float(media_element.find("offsety").text)
    media_height = float(media_element.find("height").text)

    trim_offsetx = float(trim_element.find("offsetx").text)
    trim_offsety = float(trim_element.find("offsety").text)

    roi_height = float(trim_element.find("height").text) * point_to_pixel
    roi_width = float(trim_element.find("width").text) * point_to_pixel

    # our local (0,0) at bottom left corner, opencv hat (0,0) on top left corner. 
    roi_y_bottom_left = (trim_offsety -media_offsety)
    roi_y = (media_height - roi_y_bottom_left) * point_to_pixel
    roi_y = roi_y-roi_height
    roi_x = (trim_offsetx - media_offsetx) * point_to_pixel


    return [int(i) for i in [roi_x, roi_y, roi_width, roi_height]] 



# def check_dimension(dimension_1, dimension_2, tolerance=0.02):

#     d1_max = np.max(dimension_1)
#     d2_max = np.max(dimension_2)
#     diff_max = abs((d1_max-d2_max)/d2_max)

#     d1_min = np.min(dimension_1)
#     d2_min = np.min(dimension_2)
#     diff_min = abs((d1_min-d2_min)/d2_min)

#     if ((diff_max<tolerance) and (diff_min<tolerance)):
#         return True
#     else:
#         return False


def get_daily2order_dict(excel_path):

    df = pd.read_excel(excel_path)    
    daily2order_dict =  {}

    for i in range(len(df)):
        daily_id = df.loc[i, "MEDAIGATE_DAILY"]
        order_id = df.loc[i,"MEDIAGATE_ORDER"]

        if not type(daily_id) is int:
            continue

        if type(order_id) == int:
            daily2order_dict.update({daily_id : [order_id]})
        elif type(order_id) == str:
            order_id = [int(i) for i in order_id.split(',')]
            daily2order_dict.update({daily_id : order_id})
        else:
            continue

    return daily2order_dict


def get_best_daily2order(daily2order, clip_data_path = "M:\\dockerdata\\clipData\\image_embeddings\\"):
    
    filtered_daily2order = {}

    for daily_id, order_ids in daily2order.items():
        print(f"Daily ID : {daily_id}\n\n")
        daily_npy = clip_data_path+str(daily_id)+".npy"

        if not os.path.exists(daily_npy):
            print(f"No Embedding for {daily_id}")
            continue

        daily_emb = np.load(daily_npy)
        daily_emb_norm = daily_emb/np.linalg.norm(daily_emb)
        best_match=0.9

        for order_id in order_ids:
            order_npy = clip_data_path+str(order_id)+".npy"
            if not os.path.exists(order_npy):
                print(f"No Embedding for {order_id}")
                continue
            order_emb = np.load(order_npy)
            order_emb_norm = order_emb/np.linalg.norm(order_emb)
            matching = order_emb_norm @ daily_emb_norm.T
            print(f"""
            Order ID : {order_id} 
            Match : {matching} \n \n""")

            if matching>best_match:
                best_match = matching
                filtered_daily2order.update({daily_id:order_id})
    
    return filtered_daily2order


def get_cropped_order_image(image, roi):
    x,y,w,h = roi
    if not ((w==0)or(h==0)):
        cropped_image = image[y:y+h,x:x+w,:]
    else:
        cropped_image = None
    return cropped_image



# def get_daily_xy(image, template):
#     result = cv.matchTemplate(image, template, cv.TM_CCOEFF_NORMED)
#     minVal, maxVal, minLoc, maxLoc = cv.minMaxLoc(result)
#     if maxVal>.5:
#         return maxLoc



if __name__ == "__main__":
    prio_1_csv = "C:\\Users\\rislam\\Documents\\Python Scripts\\ROI\\prio_1.csv" # daily data
    daily2order_xlsx = "C:\\Users\\rislam\\Documents\\Python Scripts\\ROI\\tagesdaten.xlsx"
    clip_data_path = "M:\\dockerdata\\clipData\\image_embeddings\\"
    server_path = "\\\\devarcsv041\\orderdata"

    prio_1_list = [id for ids in csv_to_list(prio_1_csv) for id in ids]
    
    #daily2order_all =  get_daily2order_dict(daily2order_xlsx)

    
    with open("daily2order_prio1_all.json") as f:
        daily2order_all = json.load(f)

    daily2order_p1_all = {daily:orders for daily, orders in daily2order_all.items() if str(daily) in prio_1_list}


    with open("daily2order_prio1_best_matching_embedding_0.9.json") as f:
        daily2order_p1 = json.load(f)
    
    daily2order_p1 = {v:k for k,v in daily2order_p1.items()} ## Did a mistake, reverse

    #daily2order_p1 = get_best_daily2order(daily2order_p1_all)



    df = pd.DataFrame(columns=["order_id", "order_filename", "daily_id", "daily_filename", "order_xywh", "daily_xywh","order_image.shape","daily_image.shape"])
    idx = 1


    for daily_id, order_id in daily2order_p1.items():
        try:
            order_image_path = mediagate_2_image_path(order_id, server_path)
            order_image = cv.imread(order_image_path, cv.IMREAD_COLOR)
            xml_path = get_xml_path(order_image_path)
            order_roi = get_roi(xml_path)

            cropped_image = get_cropped_order_image(order_image, order_roi)
            height, width, c = cropped_image.shape

            daily_image_path = mediagate_2_image_path(daily_id, server_path)
            daily_image = cv.imread(daily_image_path, cv.IMREAD_COLOR)
            dh,dw,dc = daily_image.shape

            # x,y = get_daily_xy(daily_image, cropped_image)

            idx+=1

            df.at[idx,"order_id"] = order_id
            df.at[idx,"order_filename"] = order_image_path
            df.at[idx,"daily_id"] = daily_id
            df.at[idx,"daily_filename"] = daily_image_path
            df.at[idx,"order_xywh"] = order_roi
            df.at[idx,"order_image.shape"] = order_image.shape
            df.at[idx,"daily_image.shape"] = daily_image.shape

            

            result = cv.matchTemplate(daily_image, cropped_image, cv.TM_CCOEFF_NORMED)
            minVal, maxVal, minLoc, maxLoc = cv.minMaxLoc(result)
            print(maxVal)
            if maxVal>.5:
                dx,dy = maxLoc
                df.at[idx,'daily_xywh'] = [dx,dy,width,height]
        
        except Exception as e:
            print("Oops!", e.__class__, "occurred.")

        if idx%10==0:
            df.to_excel("dataset_neu.xlsx")
    
    print('Finished. Press any key to continue...')
    x = input()





    


    


            



