import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# color
c = np.array([[102, 194, 165], [252, 141, 98], [141, 160, 203], 
         [231, 138, 195], [166,216,84], [255, 217, 47],
         [229, 196, 148], [179, 179, 179]])
c  = c/255

markers = ['H', '^', '>', 'D', 'o', 's']

# font
# plt.rcParams['font.sans-serif'] = 'DehaVu Sans'
plt.rcParams['font.size'] = 14

workloads = ['DRBH', 'DRBL', 'DRBM', 'DWOL', 'DWOM', 'DWOH', 'MMAPL', 'MMAPM', 'MMAPH']
fss = ['EulerFS-S', 'EulerFS', 'EXT4-dax']
t = [1, 7, 14, 21, 28, 35, 42, 49, 56]

# fig, axs = plt.subplots(1, 5, figsize=(20, 3))
# plt.setp(axs, xticks=t, xlabel='# Threads', ylabel='Throughput(Mops/s)')

# for i, workload in enumerate(workloads):
#     # plt.subplot(1, len(workloads), i + 1)
#     # plt.figure(figsize=(4,3))
#     for j, fs in enumerate(fss):
#         print(workload, fs)
#         data = pd.read_csv('out/nvme:' + fs + ':' + workload + ':directio.dat', delim_whitespace=True)
#         data = data.iloc[:,1:].values
#         axs[i].plot(t, data, color=c[j], lw=3, marker=markers[j], mec='black', markersize=8, label=fs)
    
#         axs[i].grid(axis='y', linestyle='-.')
    
#     if (i == len(workloads) - 1):
#         handles, labels = axs[i].get_legend_handles_labels()
#         fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.1), ncol=3, frameon=False)

# plt.tight_layout()
# plt.savefig('./out/subplots.png', bbox_inches = 'tight')
# plt.show()

for i, workload in enumerate(workloads):
    # plt.subplot(1, len(workloads), i + 1)
    plt.figure(figsize=(4,3))
    for j, fs in enumerate(fss):
        print(workload, fs)
        data = pd.read_csv('out/nvme:' + fs + ':' + workload + ':directio.dat', delim_whitespace=True)
        data = data.iloc[:,1:].values
        plt.plot(t, data, color=c[j], lw=3, marker=markers[j], mec='black', markersize=8, label=fs)
    
        plt.xticks(t)
        plt.xlabel('# Threads')
        plt.ylabel('Throughput(Mops/s)')
        plt.grid(axis='y', linestyle='-.')
        plt.legend(bbox_to_anchor=(0, 1.2), loc=3, borderaxespad=0, ncol=3, prop={'size':16}, frameon=False, columnspacing=0.8)
        plt.savefig('./out/' + workload + '.png', bbox_inches = 'tight')
