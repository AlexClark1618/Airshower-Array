import matplotlib.pyplot as plt
import numpy as np

def read_data(DATA:'str'):
    '''
    This function reads a provided data file and simply cleans it, strips, and splits it into a 
    list containing tuples of each timestamp
    '''
    read_data = []
    with open(DATA, 'r') as f:
        next(f) #Skip label row
        
        for line in f:
            parts = line.strip().split(';')
            
            values = tuple(int(p.strip()) for p in parts) #Converts all elements to ints for easier analysis

            if values[8]<1000000: #Ignore nonsense ns timestamps
                read_data.append(values)
        
    return read_data

def ch_grouper(DATA):
    '''
    This function splits the read data by channel number
    '''
    data = read_data(DATA)

    #Seperates data based on gps channel
    ch0_list = [tup for tup in data if tup[4]==0]
    ch1_list = [tup for tup in data if tup[4]==1]
    
    return ch0_list, ch1_list

def timestamp_ns(tup):
    """Combine ms and sub-ms into a single nanosecond timestamp"""
    return ((tup[6] * 1000000) + tup[7]) 

def data_parser(DATA):
    '''
    This function breaks the data into sections inspecting the pulse period, width, and channel time differences
    '''
    pulse_width_ch0 = []
    pulse_width_ch1 = []
    clock_period_ch0 = []
    clock_period_ch1 = []
    coincident_list = []

    ch0_list = ch_grouper(DATA)[0]
    ch1_list = ch_grouper(DATA)[1]
    #print(ch0_list)
    #print(ch1_list)

    ch0_risetimes = [timestamp_ns(tup) for tup in ch0_list if tup[2]==0]
    ch1_risetimes = [timestamp_ns(tup) for tup in ch1_list if tup[2]==0]

    ch0_risetimes = sorted(ch0_risetimes)
    ch1_risetimes = sorted(ch1_risetimes)

    clock_period_ch0.append(np.diff(ch0_risetimes))
    clock_period_ch1.append(np.diff(ch1_risetimes))       

    #Somethimes it seems to duplicate a rise or a rise or a fall.Fix:
    clock_period_ch0 = [time for time in clock_period_ch0[0] if time > set_pulse_width *2 and time < set_pulse_period * 2]
    clock_period_ch1 = [time for time in clock_period_ch1[0] if time > set_pulse_width *2 and time < set_pulse_period * 2]

    ch0_falltimes = [timestamp_ns(tup) for tup in ch0_list if tup[2]==1]
    ch1_falltimes = [timestamp_ns(tup) for tup in ch1_list if tup[2]==1]
    
    for rtime in ch0_risetimes:
        for ftime in ch0_falltimes:
            if abs(rtime - ftime) < (set_pulse_width * 2):
                dt = abs(rtime - ftime)
                pulse_width_ch0.append(dt)

    for rtime in ch1_risetimes:
        for ftime in ch1_falltimes:
            if abs(rtime - ftime) < (set_pulse_width * 2):
                dt = abs(rtime - ftime)
                pulse_width_ch1.append(dt)

    for rtime0 in ch0_risetimes:
        for rtime1 in ch1_risetimes:
            if abs(rtime0-rtime1)<1000: #1 microsecond window
                coincident_list.append(rtime0-rtime1) 

    return [(clock_period_ch0, clock_period_ch1), (pulse_width_ch0, pulse_width_ch1), coincident_list]

### Plotting Functions ###
def data_filter(DATA):
    data = np.array(DATA)

    low = np.percentile(data, min)
    high = np.percentile(data, max)

    # Filter values between 1st and 99th percentile
    filtered = data[(data >= low) & (data <= high)]
    return filtered

def clock_period_plotter(Plot_data):
    blah1 = data_filter(Plot_data[0][0])
    plt.hist(blah1, alpha = 0.5, bins = 50, align = 'left', label = "GPS Ch0") #ch0
    c0_mean = np.mean(data_filter(Plot_data[0][0]))
    c0_std = np.std(data_filter(Plot_data[0][0]))

    c0_freq = 1000000000/c0_mean
    print(f"Avg Frequency ch0 = {c0_freq:.2f}")

    blah2 = data_filter(Plot_data[0][1])
    plt.hist(blah2, alpha = 0.5, bins = 50, align = 'right', label = "GPS Ch1") #ch1
    c1_mean = np.mean(data_filter(Plot_data[0][1]))
    c1_std = np.std(data_filter(Plot_data[0][1]))

    c1_freq = 1000000000/c1_mean
    print(f"Avg Frequency ch1 = {c1_freq:.2f}")

    plt.xlabel("Period Between Pulse Risetimes (ns)")
    plt.ylabel("Frequency")
    plt.title(f"(Calibration) (Box {box_num}) Pulse Period Distribution\n Ch0 Mean:{c0_mean:.2f} | Ch0 SD: {c0_std:.2f}\n Ch1 Mean:{c1_mean:.2f} | Ch1 SD: {c1_std:.2f}")
    plt.grid(True)
    #plt.xlim(0,2000000)
    plt.legend()
    plt.show()

def pulse_width_plotter(Plot_data):
    plt.hist(data_filter(Plot_data[1][0]), alpha = 0.5, bins = 50, align = 'left', label = "GPS Ch0") #ch0
    pw0_mean = np.mean(data_filter(Plot_data[1][0]))
    pw0_std = np.std(data_filter(Plot_data[1][0]))

    plt.hist(data_filter(Plot_data[1][1]), alpha = 0.5, bins = 50, align = 'right', label = "GPS Ch1") #ch1
    pw1_mean = np.mean(data_filter(Plot_data[1][1]))
    pw1_std = np.std(data_filter(Plot_data[1][1]))

    plt.xlabel("Pulse Width (ns)")
    plt.ylabel("Frequency")
    plt.title(f"(Calibration) (Box {box_num}) Pulse Width Distribution\n Ch0 Mean: {pw0_mean:.2f} | Ch 0 SD: {pw0_std:.2f}\n Ch1 Mean: {pw1_mean:.2f} | Ch 1 SD: {pw1_std:.2f}")
    plt.grid(True)
    plt.legend()
    plt.show()

def coincidence_plotter(DATA):
    plt.hist(data_filter(Plot_data[2]), bins = 50) 
    coin_mean = np.mean(data_filter(Plot_data[2]))
    coin_std = np.std(data_filter(Plot_data[2]))

    plt.xlabel("Time Difference (Ch0-Ch1) (ns)")
    plt.ylabel("Frequency")
    plt.title(f"(Calibration) (Box {box_num}) GPS Channel Time Difference Distribution\n Mean: {coin_mean:.2f} | SD: {coin_std:.2f}")
    plt.grid(True)
    plt.show()

### Main ###
if __name__ == "__main__": 
    DATA = 'gps_daq_20251001_run5_cycle1.txt'

    box_num = 9
    set_pulse_width = 100 #In nanoseconds
    set_pulse_period = 5000000
    min = 1
    max = 99

    Plot_data = data_parser(DATA)
    clock_period_plotter(Plot_data)
    pulse_width_plotter(Plot_data)
    coincidence_plotter(Plot_data)
