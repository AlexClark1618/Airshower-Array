import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import os
from natsort import natsorted
from collections import defaultdict
from collections import Counter

#What do I want this code to do:
    #Period
    #Time over threshold
    #Coincidences with the borehole
    #Summary file

    #1/16/25:
    #Look at rates sent to data file
    #Split veto and BH coincidence events


def folder_reader(folder_path):
    global folder_files_list 
    folder_files_list = []     
    for filename in os.listdir(folder_path):
        if filename.startswith('gps_daq'):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):  # make sure it's a file
                file_name = file_path.replace("\\", "/")
                folder_files_list.append(file_name)
    return natsorted(folder_files_list) #Correctly sorted them based on number

def file_joiner():
    """
    Combines all files from a folder into a single txt file
    """
    #global folder_path
    folder_files_list= folder_reader(data_folder)
    #print(folder_files_list)
    
    with open('joined_file.txt','w') as outfile:

        for file in folder_files_list:
            print(file)
            with open(file, 'r') as infile:
                next(infile)

                for line in infile:
                    outfile.write(line)
                
    outfile.close()
    
    print("File joiner complete")
    return None

def ch_grouper(data):
    '''
    This function splits the read data by channel number
    '''
    #Seperates data based on gps channel
    ch0_list = [tup for tup in data if tup[4]==0]
    ch1_list = [tup for tup in data if tup[4]==1]
    
    return ch0_list, ch1_list

def timestamp_ns(tup):
    """Combine ms and sub-ms into a single nanosecond timestamp"""
    return ((tup[6] * 1000000) + tup[7]) 

def data_filter(DATA):
    data = np.array(DATA)

    low = np.percentile(data, min)
    high = np.percentile(data, max)

    # Filter values between 1st and 99th percentile
    filtered = data[(data >= low) & (data <= high)]
    return filtered

#DATA_FILE = 'C:\\Users\\aclark2\\Desktop\\ESP 32\\joined_file.txt' #Automatically use joined file

BH_list = []
Veto_list = []
det1_list = []
det2_list = []
det3_list = []
det4_list = []
det5_list = []
det6_list = []
det7_list = []
det8_list = []
det9_list = []
det10_list = []
all_data = []

BH_null_list = []
Veto_null_list = []
det1_null_list = []
det2_null_list = []
det3_null_list = []
det4_null_list = []
det5_null_list = []
det6_null_list = []
det7_null_list = []
det8_null_list = []
det9_null_list = []
det10_null_list = []

def read_data(data_file, single_file):

    with open(data_file, 'r') as f:
        if single_file:
            next(f)

        unique_esp_macs = []

        for line in f:
            if line.startswith('[ESP]'): #Deals with the stupid marker in run 17
                continue
            
            if line.startswith('Unknown Code'):
                continue

            parts = line.strip().split(';')
            #print(parts)
            values = tuple(int(p.strip()) for p in parts) #Converts all elements to ints for easier analysis

            if values[0]==99 and values[6]!=0: #Real data
                if values[6]<604800000 and values[7]<1000000: #Ignore nonsense ms and ns timestamps
                    all_data.append(values)

                if values[1] not in unique_esp_macs:
                    unique_esp_macs.append(values[1])

                if values[1]==48:
                    BH_list.append(values)
                if values[1]==16:
                    Veto_list.append(values)
                if values[1]==112:
                    det1_list.append(values)
                if values[1]==180:
                    det2_list.append(values)
                if values[1]==172:
                    det3_list.append(values)
                if values[1]==64:
                    det4_list.append(values)
                if values[1]==232:
                    det5_list.append(values)
                if values[1]==252:
                    det6_list.append(values)
                if values[1]==224:
                    det7_list.append(values)
                if values[1]==20:
                    det8_list.append(values)
                if values[1]==104:
                    det9_list.append(values)
                if values[1]==164:
                    det10_list.append(values)

            elif values[0]==99 and values[6]==0 and values[2]==0: #Nulls
                if values[1]==48:
                    BH_null_list.append(values)
                if values[1]==16:
                    Veto_null_list.append(values)
                if values[1]==112:
                    det1_null_list.append(values)
                if values[1]==180:
                    det2_null_list.append(values)
                if values[1]==172:
                    det3_null_list.append(values)
                if values[1]==64:
                    det4_null_list.append(values)
                if values[1]==232:
                    det5_null_list.append(values)
                if values[1]==252:
                    det6_null_list.append(values)
                if values[1]==224:
                    det7_null_list.append(values)
                if values[1]==20:
                    det8_null_list.append(values)
                if values[1]==104:
                    det9_null_list.append(values)
                if values[1]==164:
                    det10_null_list.append(values)

    print("Read data complete") 
    print(f'Unique ESPs in data file: {unique_esp_macs}')
    print(f'ESP Instance Counter:\n BH:{len(BH_list)}\n Veto:{len(Veto_list)}\n Det1:{len(det1_list)}\n Det2:{len(det2_list)}\n Det3:{len(det3_list)}\n Det4:{len(det4_list)}\n Det5:{len(det5_list)}\n Det6:{len(det6_list)}\n Det7:{len(det7_list)}\n Det8:{len(det8_list)}\n Det9:{len(det9_list)}\n Det10:{len(det10_list)}\n')

    return len(unique_esp_macs)

#read_data(DATA_FILE) #Call read data with joined file 

### Live Time Analysis ###
def live_time_calculator():
    ### Borehole ### 
    BH_ch0, BH_ch1 = ch_grouper(BH_list)

    BH_ch0_timestamps = np.array([timestamp_ns(tup) for tup in BH_ch0 if tup[2]==0]) #Only Risetimes
    BH_ch1_timestamps = np.array([timestamp_ns(tup) for tup in BH_ch1 if tup[2]==1])

    BH_lt_packet = [BH_ch0_timestamps, BH_ch1_timestamps]

    ### Det 1 ###
    det1_ch0, det1_ch1 = ch_grouper(det1_list)

    det1_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det1_ch0 if tup[2]==0]) #Only Risetimes
    det1_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det1_ch1 if tup[2]==1])

    det1_lt_packet = [det1_ch0_timestamps, det1_ch1_timestamps]

    ### Det 2 ###
    det2_ch0, det2_ch1 = ch_grouper(det2_list)

    det2_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det2_ch0 if tup[2]==0]) #Only Risetimes
    det2_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det2_ch1 if tup[2]==1])
  
    det2_lt_packet = [det2_ch0_timestamps, det2_ch1_timestamps]

    ### Det 3 ###
    det3_ch0, det3_ch1 = ch_grouper(det3_list)

    det3_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det3_ch0 if tup[2]==0]) #Only Risetimes
    det3_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det3_ch1 if tup[2]==1])

    det3_lt_packet = [det3_ch0_timestamps, det3_ch1_timestamps]

    ### Det 4 ###
    det4_ch0, det4_ch1 = ch_grouper(det4_list)

    det4_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det4_ch0 if tup[2]==0]) #Only Risetimes
    det4_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det4_ch1 if tup[2]==1])

    det4_lt_packet = [det4_ch0_timestamps, det4_ch1_timestamps]

    ### Det 5 ###
    det5_ch0, det5_ch1 = ch_grouper(det5_list)

    det5_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det5_ch0 if tup[2]==0]) #Only Risetimes
    det5_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det5_ch1 if tup[2]==1])

    det5_lt_packet = [det5_ch0_timestamps, det5_ch1_timestamps]

    ### Det 6 ###
    det6_ch0, det6_ch1 = ch_grouper(det6_list)

    det6_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det6_ch0 if tup[2]==0]) #Only Risetimes
    det6_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det6_ch1 if tup[2]==1])

    det6_lt_packet = [det6_ch0_timestamps, det6_ch1_timestamps]

    ### Det 7 ###
    det7_ch0, det7_ch1 = ch_grouper(det7_list)

    det7_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det7_ch0 if tup[2]==0]) #Only Risetimes
    det7_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det7_ch1 if tup[2]==1])

    det7_lt_packet = [det7_ch0_timestamps, det7_ch1_timestamps]

    ### Det 8 ###
    det8_ch0, det8_ch1 = ch_grouper(det8_list)

    det8_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det8_ch0 if tup[2]==0]) #Only Risetimes
    det8_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det8_ch1 if tup[2]==1])

    det8_lt_packet = [det8_ch0_timestamps, det8_ch1_timestamps]

    ### Det 9 ###
    det9_ch0, det9_ch1 = ch_grouper(det9_list)

    det9_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det9_ch0 if tup[2]==0]) #Only Risetimes
    det9_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det9_ch1 if tup[2]==1])
    
    det9_lt_packet = [det9_ch0_timestamps, det9_ch1_timestamps]

    ### Det 10 ###
    det10_ch0, det10_ch1 = ch_grouper(det10_list)

    det10_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det10_ch0 if tup[2]==0]) #Only Risetimes
    det10_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det10_ch1 if tup[2]==1]) 

    det10_lt_packet = [det10_ch0_timestamps, det10_ch1_timestamps]

    return BH_lt_packet, det1_lt_packet, det2_lt_packet, det3_lt_packet, det4_lt_packet, det5_lt_packet, det6_lt_packet, det7_lt_packet, det8_lt_packet, det9_lt_packet, det10_lt_packet

def live_time_plotter(graph):

    lt_packets = live_time_calculator()

    names_list = ['BH', 'Det1', 'Det2', 'Det3', 'Det4', 'Det5', 'Det6', 'Det7', 'Det8', 'Det9', 'Det10']
    ch_names_list = ['Ch0', 'Ch1']
    
    for i in range(len(lt_packets)):
        for j in range(len(lt_packets[0])):
            plt.scatter(np.array(range(len(lt_packets[i][j]))), lt_packets[i][j])
            plt.xlabel("Event Number")
            plt.ylabel("Timestamps (ns)")

            if len(lt_packets[i][j]>0):
                lt_packets_ymax = np.max(lt_packets[i][j])
                lt_packets_ymin = np.min(lt_packets[i][j])

                lt_packets_xmax = np.max(np.array(range(len(lt_packets[i][j]))))
                lt_packets_xmin = np.min(np.array(range(len(lt_packets[i][j]))))

                data_transfer_rate = ((lt_packets_ymax - lt_packets_ymin) / (lt_packets_xmax - lt_packets_xmin))/ 1000000000

            plt.title(f"{names_list[i]} {ch_names_list[j]} Live Time\n Data Transfer Rate: {data_transfer_rate:.2f} s")

            filename = f"{run_num}_{names_list[i]}_{ch_names_list[j]}_Live_Time.png"
            print(f'{filename} saved')
            filepath = os.path.join(save_folder, filename)
            plt.savefig(filepath, dpi=300)
            
            if graph:
                plt.show()
            
            plt.clf()    

### Period Analysis ###
def period_calculator():
    #Should do both channels
    
    ### Borehole ### 
    BH_ch0, BH_ch1 = ch_grouper(BH_list)

    BH_ch0_timestamps = np.array([timestamp_ns(tup) for tup in BH_ch0 if tup[2]==0]) #Only Risetimes
    BH_ch0_period = data_filter(np.diff(BH_ch0_timestamps))

    BH_ch0_period_mean = np.mean(BH_ch0_period)
    BH_ch0_period_median = np.median(BH_ch0_period)
    BH_ch0_period_std = np.std(BH_ch0_period)

    BH_ch1_timestamps = np.array([timestamp_ns(tup) for tup in BH_ch1 if tup[2]==1])
    BH_ch1_period = np.diff(BH_ch1_timestamps)
    BH_ch1_period_mean = np.mean(BH_ch1_period)
    BH_ch1_period_median = np.median(BH_ch1_period)
    BH_ch1_period_std = np.std(BH_ch1_period)

    BH_period_packet = [(BH_ch0_period, BH_ch0_period_mean, BH_ch0_period_median, BH_ch0_period_std),
                        (BH_ch1_period, BH_ch1_period_mean, BH_ch1_period_median, BH_ch1_period_std)]

    ### Det 1 ###
    det1_ch0, det1_ch1 = ch_grouper(det1_list)

    det1_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det1_ch0 if tup[2]==0]) #Only Risetimes
    det1_ch0_period = data_filter(np.diff(det1_ch0_timestamps))

    det1_ch0_period_mean = np.mean(det1_ch0_period)
    det1_ch0_period_median = np.median(det1_ch0_period)
    det1_ch0_period_std = np.std(det1_ch0_period)

    det1_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det1_ch1 if tup[2]==1])
    det1_ch1_period = np.diff(det1_ch1_timestamps)
    det1_ch1_period_mean = np.mean(det1_ch1_period)
    det1_ch1_period_median = np.median(det1_ch1_period)
    det1_ch1_period_std = np.std(det1_ch1_period)

    det1_period_packet = [(det1_ch0_period, det1_ch0_period_mean, det1_ch0_period_median, det1_ch0_period_std),
                        (det1_ch1_period, det1_ch1_period_mean, det1_ch1_period_median, det1_ch1_period_std)]
    
    ### Det 2 ###
    det2_ch0, det2_ch1 = ch_grouper(det2_list)

    det2_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det2_ch0 if tup[2]==0]) #Only Risetimes
    det2_ch0_period = data_filter(np.diff(det2_ch0_timestamps))

    det2_ch0_period_mean = np.mean(det2_ch0_period)
    det2_ch0_period_median = np.median(det2_ch0_period)
    det2_ch0_period_std = np.std(det2_ch0_period)

    det2_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det2_ch1 if tup[2]==1])
    det2_ch1_period = np.diff(det2_ch1_timestamps)
    det2_ch1_period_mean = np.mean(det2_ch1_period)
    det2_ch1_period_median = np.median(det2_ch1_period)
    det2_ch1_period_std = np.std(det2_ch1_period)

    det2_period_packet = [(det2_ch0_period, det2_ch0_period_mean, det2_ch0_period_median, det2_ch0_period_std),
                        (det2_ch1_period, det2_ch1_period_mean, det2_ch1_period_median, det2_ch1_period_std)]
    
    ### Det 3 ###
    det3_ch0, det3_ch1 = ch_grouper(det3_list)

    det3_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det3_ch0 if tup[2]==0]) #Only Risetimes
    det3_ch0_period = data_filter(np.diff(det3_ch0_timestamps))

    det3_ch0_period_mean = np.mean(det3_ch0_period)
    det3_ch0_period_median = np.median(det3_ch0_period)
    det3_ch0_period_std = np.std(det3_ch0_period)

    det3_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det3_ch1 if tup[2]==1])
    det3_ch1_period = np.diff(det3_ch1_timestamps)
    det3_ch1_period_mean = np.mean(det3_ch1_period)
    det3_ch1_period_median = np.median(det3_ch1_period)
    det3_ch1_period_std = np.std(det3_ch1_period)

    det3_period_packet = [(det3_ch0_period, det3_ch0_period_mean, det3_ch0_period_median, det3_ch0_period_std),
                        (det3_ch1_period, det3_ch1_period_mean, det3_ch1_period_median, det3_ch1_period_std)]
    
    ### Det 4 ###
    det4_ch0, det4_ch1 = ch_grouper(det4_list)

    det4_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det4_ch0 if tup[2]==0]) #Only Risetimes
    det4_ch0_period = data_filter(np.diff(det4_ch0_timestamps))

    det4_ch0_period_mean = np.mean(det4_ch0_period)
    det4_ch0_period_median = np.median(det4_ch0_period)
    det4_ch0_period_std = np.std(det4_ch0_period)

    det4_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det4_ch1 if tup[2]==1])
    det4_ch1_period = np.diff(det4_ch1_timestamps)
    det4_ch1_period_mean = np.mean(det4_ch1_period)
    det4_ch1_period_median = np.median(det4_ch1_period)
    det4_ch1_period_std = np.std(det4_ch1_period)

    det4_period_packet = [(det4_ch0_period, det4_ch0_period_mean, det4_ch0_period_median, det4_ch0_period_std),
                        (det4_ch1_period, det4_ch1_period_mean, det4_ch1_period_median, det4_ch1_period_std)]
    
    ### Det 5 ###
    det5_ch0, det5_ch1 = ch_grouper(det5_list)

    det5_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det5_ch0 if tup[2]==0]) #Only Risetimes
    det5_ch0_period = data_filter(np.diff(det5_ch0_timestamps))

    det5_ch0_period_mean = np.mean(det5_ch0_period)
    det5_ch0_period_median = np.median(det5_ch0_period)
    det5_ch0_period_std = np.std(det5_ch0_period)

    det5_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det5_ch1 if tup[2]==1])
    det5_ch1_period = np.diff(det5_ch1_timestamps)
    det5_ch1_period_mean = np.mean(det5_ch1_period)
    det5_ch1_period_median = np.median(det5_ch1_period)
    det5_ch1_period_std = np.std(det5_ch1_period)

    det5_period_packet = [(det5_ch0_period, det5_ch0_period_mean, det5_ch0_period_median, det5_ch0_period_std),
                        (det5_ch1_period, det5_ch1_period_mean, det5_ch1_period_median, det5_ch1_period_std)]
    
    ### Det 6 ###
    det6_ch0, det6_ch1 = ch_grouper(det6_list)

    det6_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det6_ch0 if tup[2]==0]) #Only Risetimes
    det6_ch0_period = data_filter(np.diff(det6_ch0_timestamps))

    det6_ch0_period_mean = np.mean(det6_ch0_period)
    det6_ch0_period_median = np.median(det6_ch0_period)
    det6_ch0_period_std = np.std(det6_ch0_period)

    det6_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det6_ch1 if tup[2]==1])
    det6_ch1_period = np.diff(det6_ch1_timestamps)
    det6_ch1_period_mean = np.mean(det6_ch1_period)
    det6_ch1_period_median = np.median(det6_ch1_period)
    det6_ch1_period_std = np.std(det6_ch1_period)

    det6_period_packet = [(det6_ch0_period, det6_ch0_period_mean, det6_ch0_period_median, det6_ch0_period_std),
                        (det6_ch1_period, det6_ch1_period_mean, det6_ch1_period_median, det6_ch1_period_std)]
    
    ### Det 7 ###
    det7_ch0, det7_ch1 = ch_grouper(det7_list)

    det7_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det7_ch0 if tup[2]==0]) #Only Risetimes
    det7_ch0_period = data_filter(np.diff(det7_ch0_timestamps))

    det7_ch0_period_mean = np.mean(det7_ch0_period)
    det7_ch0_period_median = np.median(det7_ch0_period)
    det7_ch0_period_std = np.std(det7_ch0_period)

    det7_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det7_ch1 if tup[2]==1])
    det7_ch1_period = np.diff(det7_ch1_timestamps)
    det7_ch1_period_mean = np.mean(det7_ch1_period)
    det7_ch1_period_median = np.median(det7_ch1_period)
    det7_ch1_period_std = np.std(det7_ch1_period)

    det7_period_packet = [(det7_ch0_period, det7_ch0_period_mean, det7_ch0_period_median, det7_ch0_period_std),
                        (det7_ch1_period, det7_ch1_period_mean, det7_ch1_period_median, det7_ch1_period_std)]
    
    ### Det 8 ###
    det8_ch0, det8_ch1 = ch_grouper(det8_list)

    det8_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det8_ch0 if tup[2]==0]) #Only Risetimes
    det8_ch0_period = data_filter(np.diff(det8_ch0_timestamps))

    det8_ch0_period_mean = np.mean(det8_ch0_period)
    det8_ch0_period_median = np.median(det8_ch0_period)
    det8_ch0_period_std = np.std(det8_ch0_period)

    det8_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det8_ch1 if tup[2]==1])
    det8_ch1_period = np.diff(det8_ch1_timestamps)
    det8_ch1_period_mean = np.mean(det8_ch1_period)
    det8_ch1_period_median = np.median(det8_ch1_period)
    det8_ch1_period_std = np.std(det8_ch1_period)

    det8_period_packet = [(det8_ch0_period, det8_ch0_period_mean, det8_ch0_period_median, det8_ch0_period_std),
                        (det8_ch1_period, det8_ch1_period_mean, det8_ch1_period_median, det8_ch1_period_std)]
    
    ### Det 9 ###
    det9_ch0, det9_ch1 = ch_grouper(det9_list)

    det9_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det9_ch0 if tup[2]==0]) #Only Risetimes
    det9_ch0_period = data_filter(np.diff(det9_ch0_timestamps))

    det9_ch0_period_mean = np.mean(det9_ch0_period)
    det9_ch0_period_median = np.median(det9_ch0_period)
    det9_ch0_period_std = np.std(det9_ch0_period)

    det9_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det9_ch1 if tup[2]==1])
    det9_ch1_period = np.diff(det9_ch1_timestamps)
    det9_ch1_period_mean = np.mean(det9_ch1_period)
    det9_ch1_period_median = np.median(det9_ch1_period)
    det9_ch1_period_std = np.std(det9_ch1_period)

    det9_period_packet = [(det9_ch0_period, det9_ch0_period_mean, det9_ch0_period_median, det9_ch0_period_std),
                        (det9_ch1_period, det9_ch1_period_mean, det9_ch1_period_median, det9_ch1_period_std)]
    
    ### Det 10 ###
    det10_ch0, det10_ch1 = ch_grouper(det10_list)

    det10_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det10_ch0 if tup[2]==0]) #Only Risetimes
    det10_ch0_period = data_filter(np.diff(det10_ch0_timestamps))

    det10_ch0_period_mean = np.mean(det10_ch0_period)
    det10_ch0_period_median = np.median(det10_ch0_period)
    det10_ch0_period_std = np.std(det10_ch0_period)

    det10_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det10_ch1 if tup[2]==1])
    det10_ch1_period = np.diff(det10_ch1_timestamps)
    det10_ch1_period_mean = np.mean(det10_ch1_period)
    det10_ch1_period_median = np.median(det10_ch1_period)
    det10_ch1_period_std = np.std(det10_ch1_period)

    det10_period_packet = [(det10_ch0_period, det10_ch0_period_mean, det10_ch0_period_median, det10_ch0_period_std),
                        (det10_ch1_period, det10_ch1_period_mean, det10_ch1_period_median, det10_ch1_period_std)]
   
    return BH_period_packet, det1_period_packet, det2_period_packet, det3_period_packet, det4_period_packet, det5_period_packet, det6_period_packet, det7_period_packet, det8_period_packet, det9_period_packet, det10_period_packet

def period_plotter(graph):

    period_packets = period_calculator()

    names_list = ['BH', 'Det1', 'Det2', 'Det3', 'Det4', 'Det5', 'Det6', 'Det7', 'Det8', 'Det9', 'Det10']
    ch_names_list = ['Ch0', 'Ch1']

    for i in range(len(period_packets)):
        for j in range(len(period_packets[0])):
            plt.hist(period_packets[i][j][0],bins = 100)
            plt.title(f"{names_list[i]} {ch_names_list[j]} Period Distribution \n Mean = {period_packets[i][j][1]:.2f} | Median = {period_packets[i][j][2]:.2f} | STD = {period_packets[i][j][3]:.2f}")
            plt.ylabel("Frequency")
            plt.xlabel("Period (ns)")

            filename = f"{run_num}_{names_list[i]}_{ch_names_list[j]}_Period_Distribution.png"
            print(f'{filename} saved')
            filepath = os.path.join(save_folder, filename)
            plt.savefig(filepath, dpi=300)

            if graph:
                plt.show()
            
            plt.clf()    

### Time of threshold Analysis ###
def time_over_thres_calculator():

    ###BH###
    BH_ch0, BH_ch1 = ch_grouper(BH_list)
    BH_ch0_timestamps = np.array([timestamp_ns(tup) for tup in BH_ch0]) 
    BH_ch1_timestamps = np.array([timestamp_ns(tup) for tup in BH_ch1])

    BH_ch0_tot = np.diff(BH_ch0_timestamps) 
    #print(len(BH_ch0_tot))
    BH_ch0_tot = data_filter(BH_ch0_tot[BH_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    #print(len(BH_ch0_tot))
    BH_ch0_tot_mean = np.mean(BH_ch0_tot)
    BH_ch0_tot_std  = np.std(BH_ch0_tot)

    BH_ch1_tot = np.diff(BH_ch1_timestamps)
    BH_ch1_tot = BH_ch1_tot[BH_ch1_tot<10000]
    BH_ch1_tot_mean = np.mean(BH_ch1_tot)
    BH_ch1_tot_std  = np.std(BH_ch1_tot)

    BH_tot_packet = [(BH_ch0_tot, BH_ch0_tot_mean, BH_ch0_tot_std),
                     (BH_ch1_tot, BH_ch1_tot_mean, BH_ch1_tot_std)]

    ###Det1###
    det1_ch0, det1_ch1 = ch_grouper(det1_list)
    det1_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det1_ch0]) 
    det1_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det1_ch1])

    det1_ch0_tot = np.diff(det1_ch0_timestamps)

    print("det1", len(det1_ch0_tot[det1_ch0_tot<10000]))
 
    det1_ch0_tot = data_filter(det1_ch0_tot[det1_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    print("det1", len(det1_ch0_tot))

    det1_ch0_tot_mean = np.mean(det1_ch0_tot)
    det1_ch0_tot_std  = np.std(det1_ch0_tot)

    det1_ch1_tot = np.diff(det1_ch1_timestamps)
    det1_ch1_tot = det1_ch1_tot[det1_ch1_tot<10000]
    det1_ch1_tot_mean = np.mean(det1_ch1_tot)
    det1_ch1_tot_std  = np.std(det1_ch1_tot)

    det1_tot_packet = [(det1_ch0_tot, det1_ch0_tot_mean, det1_ch0_tot_std),
                     (det1_ch1_tot, det1_ch1_tot_mean, det1_ch1_tot_std)]
    ###Det2###
    det2_ch0, det2_ch1 = ch_grouper(det2_list)
    det2_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det2_ch0]) #Only Risetimes
    det2_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det2_ch1])

    det2_ch0_tot = np.diff(det2_ch0_timestamps) 
    det2_ch0_tot = data_filter(det2_ch0_tot[det2_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    print(len(det2_ch0_tot))

    det2_ch0_tot_mean = np.mean(det2_ch0_tot)
    det2_ch0_tot_std  = np.std(det2_ch0_tot)

    det2_ch1_tot = np.diff(det2_ch1_timestamps)
    det2_ch1_tot = det2_ch1_tot[det2_ch1_tot<10000]
    det2_ch1_tot_mean = np.mean(det2_ch1_tot)
    det2_ch1_tot_std  = np.std(det2_ch1_tot)

    det2_tot_packet = [(det2_ch0_tot, det2_ch0_tot_mean, det2_ch0_tot_std),
                     (det2_ch1_tot, det2_ch1_tot_mean, det2_ch1_tot_std)]

    ###Det3###
    det3_ch0, det3_ch1 = ch_grouper(det3_list)
    det3_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det3_ch0]) #Only Risetimes
    det3_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det3_ch1])

    det3_ch0_tot = np.diff(det3_ch0_timestamps) 
    det3_ch0_tot = data_filter(det3_ch0_tot[det3_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    print(len(det3_ch0_tot))

    det3_ch0_tot_mean = np.mean(det3_ch0_tot)
    det3_ch0_tot_std  = np.std(det3_ch0_tot)

    det3_ch1_tot = np.diff(det3_ch1_timestamps)
    det3_ch1_tot = det3_ch1_tot[det3_ch1_tot<10000]
    det3_ch1_tot_mean = np.mean(det3_ch1_tot)
    det3_ch1_tot_std  = np.std(det3_ch1_tot)

    det3_tot_packet = [(det3_ch0_tot, det3_ch0_tot_mean, det3_ch0_tot_std),
                     (det3_ch1_tot, det3_ch1_tot_mean, det3_ch1_tot_std)]

    ###Det4###
    det4_ch0, det4_ch1 = ch_grouper(det4_list)
    det4_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det4_ch0]) #Only Risetimes
    det4_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det4_ch1])

    det4_ch0_tot = np.diff(det4_ch0_timestamps) 
    det4_ch0_tot = data_filter(det4_ch0_tot[det4_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    #print(len(det4_ch0_tot))
    det4_ch0_tot_mean = np.mean(det4_ch0_tot)
    det4_ch0_tot_std  = np.std(det4_ch0_tot)

    det4_ch1_tot = np.diff(det4_ch1_timestamps)
    det4_ch1_tot = det4_ch1_tot[det4_ch1_tot<10000]
    det4_ch1_tot_mean = np.mean(det4_ch1_tot)
    det4_ch1_tot_std  = np.std(det4_ch1_tot)

    det4_tot_packet = [(det4_ch0_tot, det4_ch0_tot_mean, det4_ch0_tot_std),
                     (det4_ch1_tot, det4_ch1_tot_mean, det4_ch1_tot_std)]

    ###Det5###
    det5_ch0, det5_ch1 = ch_grouper(det5_list)
    det5_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det5_ch0]) #Only Risetimes
    det5_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det5_ch1])

    det5_ch0_tot = np.diff(det5_ch0_timestamps) 
    det5_ch0_tot = data_filter(det5_ch0_tot[det5_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    print(len(det5_ch0_tot))
    det5_ch0_tot_mean = np.mean(det5_ch0_tot)
    det5_ch0_tot_std  = np.std(det5_ch0_tot)

    det5_ch1_tot = np.diff(det5_ch1_timestamps)
    det5_ch1_tot = det5_ch1_tot[det5_ch1_tot<10000]
    det5_ch1_tot_mean = np.mean(det5_ch1_tot)
    det5_ch1_tot_std  = np.std(det5_ch1_tot)

    det5_tot_packet = [(det5_ch0_tot, det5_ch0_tot_mean, det5_ch0_tot_std),
                     (det5_ch1_tot, det5_ch1_tot_mean, det5_ch1_tot_std)]

    ###Det6###
    det6_ch0, det6_ch1 = ch_grouper(det6_list)
    det6_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det6_ch0]) #Only Risetimes
    det6_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det6_ch1])

    det6_ch0_tot = np.diff(det6_ch0_timestamps) 
    det6_ch0_tot = data_filter(det6_ch0_tot[det6_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    det6_ch0_tot_mean = np.mean(det6_ch0_tot)
    det6_ch0_tot_std  = np.std(det6_ch0_tot)

    det6_ch1_tot = np.diff(det6_ch1_timestamps)
    det6_ch1_tot = det6_ch1_tot[det6_ch1_tot<10000]
    det6_ch1_tot_mean = np.mean(det6_ch1_tot)
    det6_ch1_tot_std  = np.std(det6_ch1_tot)

    det6_tot_packet = [(det6_ch0_tot, det6_ch0_tot_mean, det6_ch0_tot_std),
                     (det6_ch1_tot, det6_ch1_tot_mean, det6_ch1_tot_std)]

    ###Det7###
    det7_ch0, det7_ch1 = ch_grouper(det7_list)
    det7_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det7_ch0]) #Only Risetimes
    det7_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det7_ch1])

    det7_ch0_tot = np.diff(det7_ch0_timestamps) 
    det7_ch0_tot = data_filter(det7_ch0_tot[det7_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    det7_ch0_tot_mean = np.mean(det7_ch0_tot)
    det7_ch0_tot_std  = np.std(det7_ch0_tot)

    det7_ch1_tot = np.diff(det7_ch1_timestamps)
    det7_ch1_tot = det7_ch1_tot[det7_ch1_tot<10000]
    det7_ch1_tot_mean = np.mean(det7_ch1_tot)
    det7_ch1_tot_std  = np.std(det7_ch1_tot)

    det7_tot_packet = [(det7_ch0_tot, det7_ch0_tot_mean, det7_ch0_tot_std),
                     (det7_ch1_tot, det7_ch1_tot_mean, det7_ch1_tot_std)]

    ###Det8###
    det8_ch0, det8_ch1 = ch_grouper(det8_list)
    det8_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det8_ch0]) #Only Risetimes
    det8_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det8_ch1])

    det8_ch0_tot = np.diff(det8_ch0_timestamps) 
    det8_ch0_tot = data_filter(det8_ch0_tot[det8_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    det8_ch0_tot_mean = np.mean(det8_ch0_tot)
    det8_ch0_tot_std  = np.std(det8_ch0_tot)

    det8_ch1_tot = np.diff(det8_ch1_timestamps)
    det8_ch1_tot = det8_ch1_tot[det8_ch1_tot<10000]
    det8_ch1_tot_mean = np.mean(det8_ch1_tot)
    det8_ch1_tot_std  = np.std(det8_ch1_tot)

    det8_tot_packet = [(det8_ch0_tot, det8_ch0_tot_mean, det8_ch0_tot_std),
                     (det8_ch1_tot, det8_ch1_tot_mean, det8_ch1_tot_std)]

    ###Det9###
    det9_ch0, det9_ch1 = ch_grouper(det9_list)
    det9_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det9_ch0]) #Only Risetimes
    det9_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det9_ch1])

    det9_ch0_tot = np.diff(det9_ch0_timestamps) 
    det9_ch0_tot = data_filter(det9_ch0_tot[det9_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    det9_ch0_tot_mean = np.mean(det9_ch0_tot)
    det9_ch0_tot_std  = np.std(det9_ch0_tot)

    det9_ch1_tot = np.diff(det9_ch1_timestamps)
    det9_ch1_tot = det9_ch1_tot[det9_ch1_tot<10000]
    det9_ch1_tot_mean = np.mean(det9_ch1_tot)
    det9_ch1_tot_std  = np.std(det9_ch1_tot)

    det9_tot_packet = [(det9_ch0_tot, det9_ch0_tot_mean, det9_ch0_tot_std),
                     (det9_ch1_tot, det9_ch1_tot_mean, det9_ch1_tot_std)]

    ###Det10###
    det10_ch0, det10_ch1 = ch_grouper(det10_list)
    det10_ch0_timestamps = np.array([timestamp_ns(tup) for tup in det10_ch0]) #Only Risetimes
    det10_ch1_timestamps = np.array([timestamp_ns(tup) for tup in det10_ch1])

    det10_ch0_tot = np.diff(det10_ch0_timestamps) 
    det10_ch0_tot = data_filter(det10_ch0_tot[det10_ch0_tot<10000])#Lets assume there is a scenario when a rise or fall is missing, thats why I put a liberal limit of 10us
    det10_ch0_tot_mean = np.mean(det10_ch0_tot)
    det10_ch0_tot_std  = np.std(det10_ch0_tot)

    det10_ch1_tot = np.diff(det10_ch1_timestamps)
    det10_ch1_tot = det10_ch1_tot[det10_ch1_tot<10000]
    det10_ch1_tot_mean = np.mean(det10_ch1_tot)
    det10_ch1_tot_std  = np.std(det10_ch1_tot)

    det10_tot_packet = [(det10_ch0_tot, det10_ch0_tot_mean, det10_ch0_tot_std),
                     (det10_ch1_tot, det10_ch1_tot_mean, det10_ch1_tot_std)]

    return BH_tot_packet, det1_tot_packet, det2_tot_packet, det3_tot_packet, det4_tot_packet, det5_tot_packet, det6_tot_packet, det7_tot_packet, det8_tot_packet, det9_tot_packet, det10_tot_packet

def tot_plotter(graph):

    tot_packets = time_over_thres_calculator()

    names_list = ['BH', 'Det1', 'Det2', 'Det3', 'Det4', 'Det5', 'Det6', 'Det7', 'Det8', 'Det9', 'Det10']
    ch_names_list = ['Ch0', 'Ch1']

    for i in range(len(tot_packets)):
        for j in range(len(tot_packets[0])):
            plt.hist(tot_packets[i][j][0],bins = 100)
            plt.title(f"{names_list[i]} {ch_names_list[j]} T.o.T Distribution \n Mean = {tot_packets[i][j][1]:.2f} | STD = {tot_packets[i][j][2]:.2f}") #| Median = {tot_packets[i][j][2]:.2f}
            plt.ylabel("Frequency")
            plt.xlabel("Time Over Threshold (ns)")

            filename = f"{run_num}_{names_list[i]}_{ch_names_list[j]}_T.o.T._Distribution.png"
            print(f'{filename} saved')
            filepath = os.path.join(save_folder, filename)
            plt.savefig(filepath, dpi=300)

            if graph:
                plt.show()
            
            plt.clf()    

### Coincidence Analysis ###   
def coincidence_finder():

    ###Convert all data to nanosecond timestamps###
    ns_all_data=[]
    for tup in all_data:
        if tup[2]==0: #Only risetimes
            ns_all_data.append((tup[1],timestamp_ns(tup)))

    ns_all_data = np.array(ns_all_data)

    device_ids = ns_all_data[:, 0]
    timestamps = ns_all_data[:, 1]
    #print(device_ids)

    # --- Separate timestamps by device ---
    devices = defaultdict(list)
    for dev, ts in zip(device_ids, timestamps):
        devices[dev].append(ts)
    # Convert to sorted numpy arrays
    for dev in devices:
        devices[dev] = np.sort(np.array(devices[dev], dtype=float))
    #print(devices)

    # --- Coincidence detection ---
    targets = [48, 16]        # ESP 48
    Veto_Δt = 4000      # Coincidence within 1us
    BH_Δt = 400      # Coincidence within 1us
    coincidences = []

    for target in targets:
        if target == 16:
            Δt = Veto_Δt
        if target == 48:
            Δt = BH_Δt  

        if target not in devices:
            continue

        t_target = devices[target]
        #print(t48)
        for t in t_target:
            involved = [target]
            for dev, ts in devices.items():
                if dev == target:
                    continue
                # Find timestamps within [t - Δt, t + Δt]
                left = np.searchsorted(ts, t - Δt, side='left')
                right = np.searchsorted(ts, t + Δt, side='right')
                if right > left:
                    #print(ts[left:right])
                    involved.append(dev)
            if len(involved) >= 2:
                coincidences.append((t, involved))
    print(coincidences)
    print(f"Found {len(coincidences)} coincidences with ≥2 devices")
    for t, devs in coincidences[:10]:
        print(f"t={t} -> devices={devs}")
    
    num_dets = [len(devs) for _, devs in coincidences]

    # Count occurrences
    counts = Counter(num_dets)
    print("Counts", (counts.keys(), counts.values()))
    print(counts)
    # Print summary
    coin = 0
    for num, freq in sorted(counts.items()):
        print(f"{num} devices: {freq} coincidences")
        if num >= 4: #5 fold
            coin+=freq
    print(coin)
    print(coin/len(folder_files_list))    
    return counts, coin

def coincidence_plotter():
    
    counts, coin = coincidence_finder()

    plt.bar(counts.keys(), counts.values())
    plt.title(f"GPS DAQ Coincidences\n {coin} 4+ Coincidences\n Coincidence Rate Per Hour=~{coin/len(folder_files_list)}")
    plt.xlabel("Number of Detectors Involved in Coincidence Event")
    plt.yscale('log')
    plt.ylabel("Frequency")

    filename = f"{run_num} GPS_DAQ_Coincidences.png"
    filepath = os.path.join(save_folder, filename)
    plt.savefig(filepath, dpi=300)

    plt.show()
    plt.clf()   

def coincidence_per_file(div):
    
    folder_files_list= folder_reader(data_folder)

    coins_per_file = []
    unique_esp_macs_per_file = []

    for i in range(len(folder_files_list)):
        if i%div==0:
            all_data.clear() #Clear all data to prevent duplicates
            print(folder_files_list[i])
            unique_esp_macs_per_file.append(read_data(folder_files_list[i], True))
            counts, coins = coincidence_finder()
            coins_per_file.append((sum(counts.values()), coins))
     
    print("Unique esps per file:", unique_esp_macs_per_file)
    """    
    for file in folder_files_list:
        read_data(file, True)
        counts, coins = coincidence_finder()
        coins_per_file.append((counts[2], coins))"""
    
    print(coins_per_file)

    for i in range(len(coins_per_file)):
        color = cm.tab10(i % 10)
        
        plt.scatter(i+1, coins_per_file[i][0], color = color, marker = 'o', label = 'Total' if i == 0 else "")
        plt.scatter(i+1, coins_per_file[i][1], color = color, marker = 'x', label = '4-Fold' if i == 0 else "")

    plt.title(f"{run_num} Coincidences Per File")
    plt.xlabel("File Cycle Number")
    plt.ylabel("Frequency")
    plt.legend()

    filename = f"{run_num} GPS_DAQ_Coincidences_Per_Cycle.png"
    filepath = os.path.join(save_folder, filename)
    plt.savefig(filepath, dpi=300)

    plt.show()

def integrity_plotter(cycle_start, cycle_end, data):

    fig, axes = plt.subplots(10, 1, sharex=True)

    data_arr = np.array(data)
    cycles = np.arange(cycle_start, cycle_end+1)
  
    for i in range(10):
        axes[i].plot(cycles, data_arr[:, i])
        axes[i].set_ylabel(f"Det {i+1}")
        axes[i].set_ylim(0.98, 1.02)

    axes[-1].set_xlabel("Cycle #")
    plt.tight_layout(rect=[0, 0, 1, 0.1])
    fig.suptitle(f"Detector Integrity per Cycle | {run_num}", fontsize=10, y=0.98)

    filename = f"{run_num} Data_Integrity_Per_Cycle.png"
    filepath = os.path.join(save_folder, filename)
    plt.savefig(filepath, dpi=300)

    plt.show()

def rate_plotter(cycle_start, cycle_end, data):

    fig, axes = plt.subplots(12, 1, sharex=True)

    data_arr = np.array(data)
    cycles = np.arange(cycle_start, cycle_end+1)
    
    for i in range(12):
        axes[i].plot(cycles, data_arr[:, i])

        if i==0:
            axes[i].set_ylabel(f"BH")
        elif i==1:
            axes[i].set_ylabel(f"Veto")
        else:
            axes[i].set_ylabel(f"Det {i-1}")

    axes[-1].set_xlabel("Cycle #")
    plt.tight_layout(rect=[0, 0, 1, 0.1])
    fig.suptitle(f"Detector Rate per Cycle | {run_num}", fontsize=10, y=0.98)

    filename = f"{run_num} Detector_Rate_Per_Cycle.png"
    filepath = os.path.join(save_folder, filename)
    plt.savefig(filepath, dpi=300)

    plt.show()

def real_null_counter_plotter(cycle_start, cycle_end, data1, data2):
    fig, axes = plt.subplots(10, 1, sharex=True)

    data_arr1 = np.array(data1) #real
    data_arr2 = np.array(data2) #null

    data_arr3 = data_arr1/data_arr2
    cycles = np.arange(cycle_start, cycle_end+1)
  
    for i in range(5):
        axes[2*i].scatter(cycles, data_arr1[:, i])
        axes[2*i].scatter(cycles, data_arr2[:, i])

        axes[2*i].set_ylabel(f"Det {i+1}")
        axes[2*i].set_ylim(4000, 12000)
    
    for i in range(5):
        axes[2*i+1].scatter(cycles, data_arr3[:, i])
        axes[2*i+1].set_ylabel(f"Det {i+1}")

 
    axes[-1].set_xlabel("Cycle #")
    plt.tight_layout(rect=[0, 0, 1, 0.1])
    fig.suptitle(f"Real vs Null Count per Cycle (Part 1) | {run_num}", fontsize=10, y=0.98)

    filename = f"{run_num} Real_Null_Data_Per_Cycle_(Part1).png"
    filepath = os.path.join(save_folder, filename)
    plt.savefig(filepath, dpi=300)

    plt.show()

    ##############################################

    fig, axes = plt.subplots(10, 1, sharex=True)

    data_arr1 = np.array(data1)
    data_arr2 = np.array(data2)
    cycles = np.arange(cycle_start, cycle_end+1)
    
    for i in range(5):
        axes[2*i].scatter(cycles, data_arr1[:, i+5])
        axes[2*i].scatter(cycles, data_arr2[:, i+5])

        axes[2*i].set_ylabel(f"Det {i+6}")
        axes[2*i].set_ylim(4000, 12000)
    
    for i in range(5):
        axes[2*i+1].scatter(cycles, data_arr3[:, i+5])
        axes[2*i+1].set_ylabel(f"Det {i+6}")
 
    axes[-1].set_xlabel("Cycle #")
    plt.tight_layout(rect=[0, 0, 1, 0.1])
    fig.suptitle(f"Real vs Null Count per Cycle (Part 2) | {run_num}", fontsize=10, y=0.98)

    filename = f"{run_num} Real_Null_Data_Per_Cycle_(Part2).png"
    filepath = os.path.join(save_folder, filename)
    plt.savefig(filepath, dpi=300)

    plt.show()

def gps_daq_health_variables(cycle_start, cycle_end, plotting):

    folder_files_list= folder_reader(data_folder)

    rate_list_per_cycle = []
    integrity_list_per_cycle = []
    real_data_list_per_cycle = []
    null_data_list_per_cycle = []



    cycle_health_stats_path = os.path.join(save_folder, "cycle_health_stats.txt")

    open(cycle_health_stats_path, 'w').close()

    for file in folder_files_list:#[cycle_start-1:cycle_end]:
        
        print(file)

        for lst in (BH_list, Veto_list, det1_list, det2_list, det3_list, det4_list, det5_list, det6_list, det7_list, det8_list, det9_list, det10_list, BH_null_list, Veto_null_list, det1_null_list, det2_null_list, det3_null_list, det4_null_list, det5_null_list, det6_null_list, det7_null_list, det8_null_list, det9_null_list, det10_null_list):
            lst.clear()

        read_data(file, True)

        BH_request_count = sum(1 for tup in BH_list if tup[2]==0 and tup[4]==0)
        BH_file_live_time = BH_request_count * 0.002
        BH_rate = BH_request_count / 3600

        Veto_request_count = sum(1 for tup in Veto_list if tup[2]==0)
        Veto_file_live_time = Veto_request_count * 0.002
        Veto_rate = Veto_request_count / 3600

        total_requests = BH_request_count + Veto_request_count
        file_live_time = BH_file_live_time + Veto_file_live_time

        det1_data_count = sum(1 for tup in det1_list if tup[2]==0)
        det1_unique_count = len(set(tup[8] for tup in det1_list)) 
        det1_null_count = len(det1_null_list)
        det1_request_replies = det1_unique_count + det1_null_count
        det1_integrity = det1_request_replies / total_requests
        det1_rate = det1_data_count / file_live_time

        det2_data_count = sum(1 for tup in det2_list if tup[2]==0)
        det2_unique_count = len(set(tup[8] for tup in det2_list)) 
        det2_null_count = len(det2_null_list)
        det2_request_replies = det2_unique_count + det2_null_count
        det2_integrity = det2_request_replies / total_requests
        det2_rate = det2_data_count / file_live_time

        det3_data_count = sum(1 for tup in det3_list if tup[2]==0)
        det3_unique_count = len(set(tup[8] for tup in det3_list)) 
        det3_null_count = len(det3_null_list)
        det3_request_replies = det3_unique_count + det3_null_count
        det3_integrity = det3_request_replies / total_requests
        det3_rate = det3_data_count / file_live_time

        det4_data_count = sum(1 for tup in det4_list if tup[2]==0)
        det4_unique_count = len(set(tup[8] for tup in det4_list)) 
        det4_null_count = len(det4_null_list)
        det4_request_replies = det4_unique_count + det4_null_count
        det4_integrity = det4_request_replies / total_requests
        det4_rate = det4_data_count / file_live_time

        det5_data_count = sum(1 for tup in det5_list if tup[2]==0)
        det5_unique_count = len(set(tup[8] for tup in det5_list)) 
        det5_null_count = len(det5_null_list)
        det5_request_replies = det5_unique_count + det5_null_count
        det5_integrity = det5_request_replies / total_requests
        det5_rate = det5_data_count / file_live_time

        det6_data_count = sum(1 for tup in det6_list if tup[2]==0)
        det6_unique_count = len(set(tup[8] for tup in det6_list)) 
        det6_null_count = len(det6_null_list)
        det6_request_replies = det6_unique_count + det6_null_count
        det6_integrity = det6_request_replies / total_requests
        det6_rate = det6_data_count / file_live_time

        det7_data_count = sum(1 for tup in det7_list if tup[2]==0)
        det7_unique_count = len(set(tup[8] for tup in det7_list)) 
        det7_null_count = len(det7_null_list)
        det7_request_replies = det7_unique_count + det7_null_count
        det7_integrity = det7_request_replies / total_requests
        det7_rate = det7_data_count / file_live_time

        det8_data_count = sum(1 for tup in det8_list if tup[2]==0)
        det8_unique_count = len(set(tup[8] for tup in det8_list)) 
        det8_null_count = len(det8_null_list)
        det8_request_replies = det8_unique_count + det8_null_count
        det8_integrity = det8_request_replies / total_requests
        det8_rate = det8_data_count / file_live_time

        det9_data_count = sum(1 for tup in det9_list if tup[2]==0)
        det9_unique_count = len(set(tup[8] for tup in det9_list)) 
        det9_null_count = len(det9_null_list)
        det9_request_replies = det9_unique_count + det9_null_count
        det9_integrity = det9_request_replies / total_requests
        det9_rate = det9_data_count / file_live_time

        det10_data_count = sum(1 for tup in det10_list if tup[2]==0)
        det10_unique_count = len(set(tup[8] for tup in det10_list)) 
        det10_null_count = len(det10_null_list)
        det10_request_replies = det10_unique_count + det10_null_count
        det10_integrity = det10_request_replies / total_requests
        det10_rate = det10_data_count / file_live_time

        health_msg = (

            f'Health Statistics for File: {file}\n'
            f'###Borehole and Veto###'
            f'\nFile Request, File Live Time, File Rate\n'
            f'{BH_request_count}, {BH_file_live_time:.2f}, {BH_rate:.2f}\n' 
            f'{Veto_request_count}, {Veto_file_live_time:.2f}, {Veto_rate:.2f}\n'

            f'\nTotal File Requests = {total_requests}\n'

            f'\nTotal File Live Time = {file_live_time:.2f}\n'
            
            f'\n###Array Detectors###'
            f'\nReal Data Count, Unique Real Data Count, Null Count, Unique Replies, File Integrity, File Rate\n'
            f'{det1_data_count}, {det1_unique_count}, {det1_null_count}, {det1_request_replies}, {det1_integrity:.2f}, {det1_rate:.2f}\n' 
            f'{det2_data_count}, {det2_unique_count}, {det2_null_count}, {det2_request_replies}, {det2_integrity:.2f}, {det2_rate:.2f}\n'  
            f'{det3_data_count}, {det3_unique_count}, {det3_null_count}, {det3_request_replies}, {det3_integrity:.2f}, {det3_rate:.2f}\n'  
            f'{det4_data_count}, {det4_unique_count}, {det4_null_count}, {det4_request_replies}, {det4_integrity:.2f}, {det4_rate:.2f}\n'  
            f'{det5_data_count}, {det5_unique_count}, {det5_null_count}, {det5_request_replies}, {det5_integrity:.2f}, {det5_rate:.2f}\n'  
            f'{det6_data_count}, {det6_unique_count}, {det6_null_count}, {det6_request_replies}, {det6_integrity:.2f}, {det6_rate:.2f}\n'  
            f'{det7_data_count}, {det7_unique_count}, {det7_null_count}, {det7_request_replies}, {det7_integrity:.2f}, {det7_rate:.2f}\n'  
            f'{det8_data_count}, {det8_unique_count}, {det8_null_count}, {det8_request_replies}, {det8_integrity:.2f}, {det8_rate:.2f}\n'  
            f'{det9_data_count}, {det9_unique_count}, {det9_null_count}, {det9_request_replies}, {det9_integrity:.2f}, {det9_rate:.2f}\n'  
            f'{det10_data_count}, {det10_unique_count}, {det10_null_count}, {det10_request_replies}, {det10_integrity:.2f}, {det10_rate:.2f}\n' 

        )

        with open(cycle_health_stats_path, 'a') as hs:
            hs.write(health_msg)
            hs.write("\n##############################################################################################################################\n\n")

        int_tup = [det1_integrity, det2_integrity, det3_integrity, det4_integrity, det5_integrity, det6_integrity, det7_integrity, det8_integrity, det9_integrity, det10_integrity]
        integrity_list_per_cycle.append(int_tup)

        rate_tup = [BH_rate, Veto_rate, det1_rate, det2_rate, det3_rate, det4_rate, det5_rate, det6_rate, det7_rate, det8_rate, det9_rate, det10_rate]
        rate_list_per_cycle.append(rate_tup)

        real_data_tup = [det1_data_count, det2_data_count, det3_data_count, det4_data_count, det5_data_count, det6_data_count, det7_data_count, det8_data_count, det9_data_count, det10_data_count]
        real_data_list_per_cycle.append(real_data_tup)

        null_data_tup = [det1_null_count, det2_null_count, det3_null_count, det4_null_count, det5_null_count, det6_null_count, det7_null_count, det8_null_count, det9_null_count, det10_null_count]
        null_data_list_per_cycle.append(null_data_tup)

    if plotting is True:
        integrity_plotter(cycle_start, cycle_end, integrity_list_per_cycle)
        rate_plotter(cycle_start, cycle_end, rate_list_per_cycle)
        real_null_counter_plotter(cycle_start, cycle_end, real_data_list_per_cycle, null_data_list_per_cycle)
        #print(health_msg)
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    #Data Filter min & max
    min = 1
    max = 99
    
    #Run ID and folder paths
    run_num = "Run 75"

    save_folder_path = 'C:\\Users\\alexc\\Desktop\\KoForce GPS DAQ\\ESP 32\\Graphs\\'
    save_folder = os.path.join(save_folder_path, run_num)

    os.makedirs(save_folder, exist_ok=True)  

    summary_file_path = os.path.join(save_folder, 'summary_file')

    data_folder_path = 'C:\\Users\\alexc\\Desktop\\KoForce GPS DAQ\\ESP 32\\GPS Data\\'
    data_folder = os.path.join(data_folder_path, run_num)

    DATA_FILE = 'C:\\Users\\alexc\\Desktop\\KoForce GPS DAQ\\ESP 32\\joined_file.txt' #Automatically use joined file

    #file_joiner()
    #read_data(DATA_FILE, False) #Call read data with joined file

    #live_time_plotter(False)
    #period_plotter(False)
    #tot_plotter(False)
    
    #coincidence_plotter()
    #coincidence_per_file(1)
    gps_daq_health_variables(1, 44, True)

"""
def file_reader_plotter(DATA: list, Mode):

    file_list = []
    measured_list = []
    eff_per_file = []


    for file in DATA: 
        det_1 = 0
        det_2 = 0
        det_3 = 0
        det_4 = 0
        det_5 = 0
        det_6 = 0
        det_7 = 0
        det_8 = 0
        det_9 = 0
        det_10 = 0
        BH = 0

        with open(file, 'r') as f:
            next(f) #Skip header

            line_count = 0 

            for line in f:
                parts = line.strip().split(';')
                
                values = tuple(int(p.strip()) for p in parts) #Converts all elements to ints for easier analysis
                
                line_count += 1 #Counts total number of lines in file

                #Counts occurances of each esp in the data file
                if values[1]==48:
                    BH += 1
                if values[1]==112:
                    det_1 += 1
                if values[1]==180:
                    det_2 += 1
                if values[1]==172:
                    det_3 += 1
                if values[1]==64:
                    det_4 += 1
                if values[1]==232:
                    det_5 += 1
                if values[1]==252:
                    det_6 += 1
                if values[1]==224:
                    det_7 += 1
                if values[1]==188:
                    det_8 += 1
                if values[1]==104:
                    det_9 += 1
                if values[1]==164:
                    det_10 += 1
                #else:
                    #print("Unknown ID")

            det_info = (BH ,det_1, det_2, det_3, det_4, det_5, det_6, det_7, det_8, det_9, det_10)
            det_info = det_info + (sum(det_info),) + (line_count,) #Just for debugging to see total number of lines = the sum of the parts

            file_list.append(file)
            measured_counts = np.array(det_info[:11])//2
            measured_list.append(measured_counts)
            #print(measured_counts)
            eff_per_file.append(measured_counts/ expected_counts)#Generate a list of statistics across multiple files 

    if Mode == 0: #For plotting single files
        for det_info, file_name in zip(measured_list, file_list):
            # Bar width and positioning for side-by-side bars
            bar_width = 0.35
            names = ['BH', 'Det1', 'Det2', 'Det3', 'Det4', 'Det5', 'Det6', 'Det7', 'Det8', 'Det9', 'Det10']
            items = np.arange(1,12)
            x = np.arange(len(items))

            plt.figure(figsize=(10, 5))

            # Plot measured and expected side-by-side
            plt.bar(x - bar_width/2, det_info, bar_width, label='Measured', alpha=0.8)
            plt.bar(x + bar_width/2, expected_counts, bar_width, label='Expected', alpha=0.8)

            # Labels and aesthetics
            plt.xticks(x, [f'{i}' for i in names])
            plt.ylabel('Count')
            plt.title(f'Measured vs Expected Counts (File:{file_name})')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.show()
    
    if Mode == 1: #For plotting average of multiple files

        eff_per_file = np.array(eff_per_file)
        
        std = np.std(eff_per_file, axis=0)

        average_effs = np.sum(eff_per_file, axis=0)/len(eff_per_file)

        # Bar width and positioning for side-by-side bars
        bar_width = 0.35
        names = ['BH', 'Det1', 'Det2', 'Det3', 'Det4', 'Det5', 'Det6', 'Det7', 'Det8', 'Det9', 'Det10']

        plt.errorbar(names, average_effs, yerr=std, fmt='o', capsize=5, ecolor='black', color='blue', markersize=6)

        plt.xlabel("Det #")
        plt.ylabel("ESP Efficiency (%)")
        plt.title("Efficiency Per Detector ESP")
        plt.grid(True)
        plt.show()
    

def read_error_log(error_file):

    reboot_time = []

    with open(error_file, 'r') as f:
        for line in f:
            line = line.strip()

            if line.startswith("[ESP]:"):

                parts = line.split(":") #Remove [ESP] marker

                parts = parts[1].strip().split(";") #Split info 

                values = tuple(int(p.strip()) for p in parts) #Convert info to integers

                if values[2] == 15: #Reboot marker
                    if values[3]<30000: #Effectively trying to ignore the first reboot, which will by nature be large
                        reboot_time.append(values[3])
        
        return reboot_time

###Main###
if __name__ == "__main__":
    BH_rate = 1.8 * 3600
    arr_rate = 1.8 * 0.002 * 3600
    
    expected_counts = np.array((BH_rate, arr_rate * 201, arr_rate*524, arr_rate*341, arr_rate*386, arr_rate*179, 
                        arr_rate*317, arr_rate*283, arr_rate*394, arr_rate*211, arr_rate*335))
    

    expected_counts = np.array((BH_rate, arr_rate * 428, arr_rate*585.6, arr_rate*375.1, arr_rate*437.1, arr_rate*307.2, 
                        arr_rate*348.7, arr_rate*518, arr_rate*455.4, arr_rate*350.2, arr_rate*478.1))

    folder_path = 'C:\\Users\\aclark2\\Desktop\\ESP 32\\GPS Data\\Run20251007'

    DATA_LIST = folder_reader(folder_path)
    print('DATA_LIST:', DATA_LIST)

    error_file = "C:\\Users\\aclark2\\Desktop\\ESP 32\\GPS Data\\Run20251008\\error_log.txt"

    file_reader_plotter(DATA_LIST, Mode = 1)


    #Reboot Deadtime          
    reboot_time = read_error_log(error_file)
    reboot_time_len = len(reboot_time)
    print(f'Total Rebbot Deadtime for Det 8: {(np.sum(reboot_time) + (10000 * reboot_time_len))/1000}')
"""
