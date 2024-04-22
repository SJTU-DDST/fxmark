import csv

# 打开log.txt文件并读取内容
with open('log.txt', 'r') as file:
    lines = file.readlines()

# 定义线程数量和FS名字列表
thread_counts = [1, 2, 4, 8, 12, 16, 20, 24, 28]
fs_names = ['EulerFS-S', 'EulerFS', 'EXT4-dax', 'NOVA', 'pmfs']
fs_name = ''
thrpts = []
# 创建CSV文件并写入表头
with open('output.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    
    # 写入横向表头
    writer.writerow(['System'] + thread_counts)


    
    # 逐行解析log.txt内容并写入CSV文件
    for i in range(len(lines)):
        line = lines[i].strip()
        
        # 跳过注释行和空行
        if '#' in line or len(line) == 0:
            if len(thrpts) > 0:
                writer.writerow([fs_name] + thrpts) #line.split()[1:])
                thrpts = []
        else:
            thrpts.append(line.split()[1])
        #     continue
        # else:
        
        # 解析文件路径、FS名字和数据行
        #out/nvme:pmfs:filebench_varmail-1k:directio.dat:1 0.22836964499999998
        # file_path, fs_name, data_line = line.split(':')
        fs_name = line.split(':')[1]

        # 跳过不在FS名字列表中的FS
        if fs_name not in fs_names:
            continue
        
        # 写入纵向表头和数据行
        # if i > 0 and lines[i-1].startswith('#'):
        # if '#' not in line:
        #     writer.writerow([fs_name] + line.split()[1:])
        # thrpts.append(line.split()[1])
        # else:
        #     writer.writerow([fs_name] + line.split())
    writer.writerow([fs_name] + thrpts) #line.split()[1:])

print("转换完成。")