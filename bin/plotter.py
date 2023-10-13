#!/usr/bin/env python3
import os
import stat
import sys
import subprocess
import optparse
import math
import pdb
from parser import Parser

import matplotlib.pyplot as plt
import numpy as np

CUR_DIR     = os.path.abspath(os.path.dirname(__file__))

"""
# GNUPLOT HOWTO
- http://www.gnuplotting.org/multiplot-placing-graphs-next-to-each-other/
- http://stackoverflow.com/questions/10397750/embedding-multiple-datasets-in-a-gnuplot-command-script
- http://ask.xmodulo.com/draw-stacked-histogram-gnuplot.html
"""

class Plotter(object):
    def __init__(self, log_file):
        (opts, args) = parser.parse_args()
        gen_dat = "gen" in opts.ty
        plot = "plotter" in opts.ty

        # config
        self.UNIT_WIDTH  = 2.3
        self.UNIT_HEIGHT = 2.3
        self.PAPER_WIDTH = 7   # USENIX text block width
        self.EXCLUDED_FS = ()  # ("tmpfs")
        self.CPU_UTILS = ["user.util",
                          "sys.util",
                          "idle.util",
                          "iowait.util"]
        self.UNIT = 1000000.0
        self.SILVERSEARCHER_UNIT = 1000.0
        self.FIO_UNIT = 1.0

        # init.
        self.log_file = log_file
        self.parser = Parser()
        self.parser.parse(self.log_file)
        if not plot:
            self.config = self._get_config()
        else:
            self.config = self._get_config_from_out() # plot NOVA & other fs together
        self.ncore = int(self.parser.get_config("PHYSICAL_CHIPS")) * \
                     int(self.parser.get_config("CORE_PER_CHIP"))
        self.out_dir  = ""
        self.out_file = ""
        self.out = 0

        # print("media", self.config["media"])
        # print("fs", self.config["fs"])
        # print("bench", self.config["bench"])
        # print("ncore", self.config["ncore"])
        # print("iomode", self.config["iomode"])

        # self._get_config_from_out() # try

    def _get_config_from_out(self):
        # check all the files ../out/{media:fs:bench:iomode}.dat to get config
        all_config = []
        config_dic = {}
        for f in os.listdir("./out/"):
            if f.endswith(".dat"):
                key = f.split(".")[0].split(":")
                for (i, k) in enumerate(key):
                    try:
                        all_config[i]
                    except IndexError:
                        all_config.append(set())
                    all_config[i].add(k)
        for (i, key) in enumerate(["media", "fs", "bench", "iomode"]):
            config_dic[key] = sorted(list(all_config[i]))
        config_dic["ncore"] = ['000000001', '000000002', '000000004', '000000008', '000000012', '000000016', '000000020', '000000024', '000000028']
        # TODO: require manual modification

        # print("media", config_dic["media"])
        # print("fs", config_dic["fs"])
        # print("bench", config_dic["bench"])
        # print("ncore", config_dic["ncore"])
        # print("iomode", config_dic["iomode"])
        return config_dic
    

    def _get_config(self):
        all_config = []
        config_dic = {}
        for kd in self.parser.search_data():
            key = kd[0]
            for (i, k) in enumerate(key):
                try:
                    all_config[i]
                except IndexError:
                    all_config.append(set())
                all_config[i].add(k)
        for (i, key) in enumerate(["media", "fs", "bench", "ncore", "iomode"]):
            config_dic[key] = sorted(list(all_config[i]))
        return config_dic

    def _gen_log_info(self):
        log_info = self.parser.config
        print("# LOG_FILE = %s" % self.log_file, file=self.out)
        for key in log_info:
            print("# %s = %s" % (key, log_info[key]), file=self.out)
        print("", file=self.out)

    def _get_pdf_name(self):
        pdf_name = self.out_file
        outs = self.out_file.split(".")
        if outs[-1] == "gp" or outs[-1] == "gnuplot":
            pdf_name = '.'.join(outs[0:-1]) + ".pdf"
        pdf_name = os.path.basename(pdf_name)
        return pdf_name

    def _get_fs_list(self, media, bench, iomode):
        # get args
        (opts, args) = parser.parse_args()
        gen_dat = "gen" in opts.ty
        plot = "plotter" in opts.ty
        
        if plot:
            # check all the files ../out/{media:fs:bench:iomode}.dat to get fs_set
            fs_set = set()
            for f in os.listdir("./out/"):
                if f.endswith(".dat"):
                    key = f.split(".")[0].split(":")
                    if key[0] == media and key[2] == bench and key[3] == iomode:
                        fs_set.add(key[1])
            return sorted(list(fs_set))
        else:
            data = self.parser.search_data([media, "*", bench, "*", iomode])
            fs_set = set()
            for kd in data:
                fs = kd[0][1]
                if fs not in self.EXCLUDED_FS:
                    fs_set.add(fs)
            #remove tmpfs - to see more acurate comparision between storage fses
    #        fs_set.remove("tmpfs");
            return sorted(list(fs_set))
        
    def _gen_pdf(self, gp_file):
        subprocess.call("cd %s; gnuplot %s" %
                        (self.out_dir, os.path.basename(gp_file)),
                        shell=True)

    def _plot_header(self):
        n_unit = len(self.config["media"]) * len(self.config["bench"])
        n_col = min(n_unit, int(self.PAPER_WIDTH / self.UNIT_WIDTH))
        n_row = math.ceil(float(n_unit) / float(n_col))
        print("set term pdfcairo size %sin,%sin font \',10\'" %
              (self.UNIT_WIDTH * n_col, self.UNIT_HEIGHT * n_row),
              file=self.out)
        print("set_out=\'set output \"`if test -z $OUT; then echo %s; else echo $OUT; fi`\"\'"
              % self._get_pdf_name(), file=self.out)
        print("eval set_out", file=self.out)
        print("set multiplot layout %s,%s" % (n_row, n_col), file=self.out)

    def _plot_footer(self):
        print("", file=self.out)
        print("unset multiplot", file=self.out)
        print("set output", file=self.out)


    def _plot_sc_data(self, media, bench, iomode):
        def _get_sc_style(fs):
            return "with lp ps 0.5"

        def _get_data_file(fs):
            return "%s:%s:%s:%s.dat" % (media, fs, bench, iomode)

        # check if there are data
        fs_list = self._get_fs_list(media, bench, iomode)
        if fs_list == []:
            return

        # gen sc data files
        for fs in fs_list:
            data = self.parser.search_data([media, fs, bench, "*", iomode])
            if data == []:
                continue
            data_file = os.path.join(self.out_dir, _get_data_file(fs))
            with open(data_file, "w") as out:
                print("# %s:%s:%s:%s:*" % (media, fs, bench, iomode), file=out)
                for d_kv in data:
                    d_kv = d_kv[1]
                    ncpu = float(d_kv["ncpu"])
                    if ncpu.is_integer():
                        ncpu = int(ncpu)
                    if ncpu > self.ncore:
                        break
                    if "fio" in bench:
                        print("%s %s" %
                            (d_kv["ncpu"], float(d_kv["works/sec"])/self.FIO_UNIT),
                            file=out)
                    elif "silversearcher" in bench:
                        print("%s %s" %
                            (d_kv["ncpu"], float(d_kv["works/sec"])/self.SILVERSEARCHER_UNIT),
                            file=out)
                    else:
                        print("%s %s" %
                            (d_kv["ncpu"], float(d_kv["works/sec"])/self.UNIT),
                            file=out)
        
        # gen gp file
        print("", file=self.out)
        # print("set title \'%s:%s:%s\'" % (media, bench, iomode), file=self.out)
        # print("set title item noenhanced")
        print("set title \'%s\'" % (bench.replace("_", " ")), file=self.out)
        print("set xlabel \'# Threads\'", file=self.out)
        if "fio" in bench:
            print("set ylabel \'%s\'" % "MiB/sec", file=self.out)
        elif "silversearcher" in bench:
            print("set ylabel \'%s\'" % "K ops/sec", file=self.out)
        else:
            print("set ylabel \'%s\'" % "M ops/sec", file=self.out)
        print("set xtics 7", file=self.out)

        fs = fs_list[0]
        print("plot [0:][0:] \'%s\' using 1:2 title \'%s\' %s"
              % (_get_data_file(fs), fs, _get_sc_style(fs)),
              end="", file=self.out)
        for fs in fs_list[1:]:
            print(", \'%s\' using 1:2 title \'%s\' %s"
                  % (_get_data_file(fs), fs, _get_sc_style(fs)),
                  end="", file=self.out)
        print("", file=self.out)

    def _plot_sc_data_matplotlib(self, media, benches, iomode, gen_dat, plot):
        def _get_sc_style(fs):
            return "with lp ps 0.5"

        def _get_data_file(fs):
            return "%s:%s:%s:%s.dat" % (media, fs, bench, iomode)
        
        fs_list = []

        if gen_dat:
            for bench in benches:
                # check if there are data
                fs_list = self._get_fs_list(media, bench, iomode)
                if fs_list == []:
                    return
                # gen sc data files
                for fs in fs_list:
                    data = self.parser.search_data([media, fs, bench, "*", iomode])
                    if data == []:
                        continue
                    data_file = os.path.join(self.out_dir, _get_data_file(fs))

                    with open(data_file, "w") as out:
                        duration = 1.0
                        for d_kv in data:
                            d_kv = d_kv[1]
                            duration = float(d_kv["secs"])
                            # print(duration)
                        print("# %s:%s:%s:%s:*:%f" % (media, fs, bench, iomode, duration), file=out) # add duration
                        for d_kv in data:
                            d_kv = d_kv[1]
                            ncpu = float(d_kv["ncpu"])
                            if ncpu.is_integer():
                                ncpu = int(ncpu)
                            if ncpu > self.ncore:
                                break
                            if "fio" in bench:
                                print("%s %s" %
                                    (d_kv["ncpu"], float(d_kv["works/sec"])/self.FIO_UNIT),
                                    file=out)
                            elif "silversearcher" in bench:
                                print("%s %s" %
                                    (d_kv["ncpu"], float(d_kv["works/sec"])/self.SILVERSEARCHER_UNIT),
                                    file=out)
                            else:
                                print("%s %s" %
                                    (d_kv["ncpu"], float(d_kv["works/sec"])/self.UNIT),
                                    file=out)
                                
        if plot:
            for bench in benches:
                # check if there are data
                fs_list = self._get_fs_list(media, bench, iomode)
                if fs_list == []:
                    print("No data for %s" % bench)
                    return
            # color
            c = np.array([[102, 194, 165], [252, 141, 98], [141, 160, 203], 
                    [231, 138, 195], [166,216,84], [255, 217, 47],
                    [229, 196, 148], [179, 179, 179]])
            c  = c/255
            markers = ['H', '^', '>', 'D', 'o', 's']
            hat = ['|//','-\\\\','|\\\\','-//',"--","\\\\",'//',"xx"]
            
            # gen gp file
            if len(benches) == 4:
                plt.rcParams.update({'font.size': 12})
                fig, axs = plt.subplots(2, 2, figsize=(8, 6))
            else:  
                fig, axs = plt.subplots(1, len(benches), figsize=(4 * len(benches), 3))
            for i, bench in enumerate(benches):
                fs_list = self._get_fs_list(media, bench, iomode)
                if fs_list == []:
                    print("No data for %s" % bench)
                    return

                if len(benches) == 1:
                    ax = axs
                elif len(benches) == 4: 
                    ax = axs[i//2][i%2]
                else:
                    ax = axs[i]
                
                fs = fs_list[0]

                dat = np.loadtxt(os.path.join(self.out_dir, _get_data_file(fs)), unpack=True)
                barplot = False
                
                # if dat[0] is not an array, set size to 1
                if not isinstance(dat[0], np.ndarray):
                    size = 1
                else:
                    size = len(dat[0])

                x = np.arange(size)
                total_width = 0.9 # 0.9
                n = len(fs_list)
                width = total_width / n
                x = x - (total_width - width) / 2

                if np.any(dat[0] % 1 != 0): # skewed, bar plot
                    barplot = True
                    # with np.printoptions(precision=3, suppress=True):
                    #     print(bench, fs, dat)

                if barplot:
                    ax.bar(x, dat[1], width=width, edgecolor='black', lw=1.2, color=c[0], hatch=hat[0], label=fs)
                else:
                    ax.plot(*np.loadtxt(os.path.join(self.out_dir, _get_data_file(fs)), unpack=True), label=fs, color=c[0], marker=markers[0], lw=3, mec='black', markersize=8, alpha=1)

                for j, fs in enumerate(fs_list[1:]):
                    # if np.any(dat[0] % 1 != 0): # skewed, bar plot
                    #     with np.printoptions(precision=3, suppress=True):
                    #         print(bench, fs, dat)

                    label_fs = fs
                    if fs == "EulerFS-S":
                        label_fs = "BorschFS"
                    elif fs == "EulerFS":
                        label_fs = "SoupFS"

                    if barplot:
                        ax.bar(x + width * (j+1), np.loadtxt(os.path.join(self.out_dir, _get_data_file(fs)), unpack=True)[1], width=width, edgecolor='black', lw=1.2, color=c[j+1], hatch=hat[j+1], label=label_fs)
                    else:
                        ax.plot(*np.loadtxt(os.path.join(self.out_dir, _get_data_file(fs)), unpack=True), label=label_fs, color=c[j+1], marker=markers[j+1], lw=3, mec='black', markersize=8, alpha=1)
                
                title = bench.replace("_", " ")
                # add (a) (b) (c) (d) before title according to i
                # if len(benches) == 4:
                title = "(" + chr(ord('a') + i) + ") " + title

                ax.set_title(title)
                ax.grid(axis='y', linestyle='-.')

                if np.any(dat[0] % 1 != 0):
                    print("float xticks found")
                    if barplot:
                        names = dat[0].astype(str)
                        names = np.where(names == "0.1", "random", names) # 1.2 means zipf, 0.1 means random, just a symbol, not for zipf parameter
                        names = np.where(names == "1.2", "skewed", names)
                        
                        ax.set_xticks(range(size))
                        ax.set_xticklabels(names)
                    else: # disabled
                        ax.set_xticks(dat[0].astype(float))
                        ax.set_xlabel("Zipf parameter")
                else:
                    ax.set_xticks(dat[0].astype(int))
                    ax.set_xlabel("# Threads")
                if "fio" in bench:
                    ax.set_ylabel("MiB/sec")
                elif "silversearcher" in bench:
                    ax.set_ylabel("K ops/sec")
                else:
                    ax.set_ylabel("M ops/sec")

                handles, labels = ax.get_legend_handles_labels()

            fig.legend(handles, labels, loc=9, ncol=len(fs_list), frameon=False)
            fig.tight_layout()
            if len(benches) == 4:
                fig.subplots_adjust(top=0.9)
            else:
                fig.subplots_adjust(top=0.8)

            save_name = "_".join(benches)
            plt.savefig(os.path.join(self.out_dir, "%s.png" % save_name))
            # plt.savefig(os.path.join(self.out_dir, "%s.svg" % save_name))
            plt.savefig(os.path.join(self.out_dir, "%s.pdf" % save_name))
            plt.close()

    def _plot_util_data(self, media, ncore, bench, iomode):
        print("", file=self.out)
        print("set grid y", file=self.out)
        print("set style data histograms", file=self.out)
        print("set style histogram rowstacked", file=self.out)
        print("set boxwidth 0.5", file=self.out)
        print("set style fill solid 1.0 border -1", file=self.out)
        print("set ytics 10", file=self.out)
        print("", file=self.out)
        print("set title \'%s:%s:*:%s:%s\'" % (media,bench, ncore, iomode), file=self.out)
        print("set xlabel \'\'", file=self.out)
        print("set ylabel \'CPU utilization\'", file=self.out)
        print("set yrange [0:100]", file=self.out)
        print("set xtics rotate by -45", file=self.out)
        print("set key out horiz", file=self.out)
        print("set key center top", file=self.out)
        print("", file=self.out)

        '''
        #    user.util sys.util idle.util iowait.util
        ext2 20        45       35        0
        xfs  10        50       40        0
        '''
        print("# %s:*:%s:%s" % (media, bench, ncore), file=self.out)
        print("plot \'-\' using 2:xtic(1) title \'%s\'"
              % self.CPU_UTILS[0].split('.')[0], end="", file=self.out)
        for (i, util) in enumerate(self.CPU_UTILS[1:]):
            print(", \'\' using %s title \'%s\'"
                  % (i+3, util.split('.')[0]),
                  end="", file=self.out)
        print("", file=self.out)

        fs_list = self._get_fs_list(media, bench, iomode)
        for _u in self.CPU_UTILS:
            print("  # %s" % self.CPU_UTILS, file=self.out)
            for fs in fs_list:
                data = self.parser.search_data([media, fs, bench, str(ncore), iomode])
                if data is None:
                    continue
                d_kv = data[0][1]

                print("  \"%s\"" % fs, end="", file=self.out)
                for util in self.CPU_UTILS:
                    print(" %s" % d_kv[util], end="", file=self.out)
                print("", file=self.out)
            print("e", file=self.out)

    def plot_sc(self, out_dir):
        self.out_dir  = out_dir
        subprocess.call("mkdir -p %s" % self.out_dir, shell=True)
        self.out_file = os.path.join(self.out_dir, "sc.gp")
        self.out = open(self.out_file, "w")
        self._gen_log_info()
        self._plot_header()
        for media in self.config["media"]:
            for bench in self.config["bench"]:
                for iomode in self.config["iomode"]:
                    self._plot_sc_data(media, bench, iomode)
        self._plot_footer()
        self.out.close()
        self._gen_pdf(self.out_file)

    def plot_sc_matplotlib(self, out_dir, gen_dat=True, plot=True):
        bench_groups = [["DRBL", "DRBM", "DRBH", "DWOL", "DWOM"], 
                       ["DWAL", "DWSL"], 
                       ["fio_zipf_sync", "fio_zipf_mmap"], 
                       ["MRDL", "MRDM"], 
                       ["MWCL", "MWCM"], 
                       ["MWRL", "MWRM"],
                       ["DWOL", "DWOM", "MWCL", "MWCM"],
                       ["filebench_varmail", "filebench_fileserver", "filebench_webproxy", "filebench_fileserver-1k"],
                       ["filebench_varmail", "filebench_oltp", "filebench_fileserver", "filebench_webserver", "filebench_webproxy", "filebench_fileserver-1k"]]
        
        self.out_dir  = out_dir
        subprocess.call("mkdir -p %s" % self.out_dir, shell=True)
        # self.out_file = os.path.join(self.out_dir, "sc.gp")
        # self.out = open(self.out_file, "w")
        # self._gen_log_info()
        # self._plot_header()
        for media in self.config["media"]:
            for bench in self.config["bench"]:
                for iomode in self.config["iomode"]:
                    self._plot_sc_data_matplotlib(media, [bench], iomode, gen_dat, plot)

        # plot group
        for media in self.config["media"]:
            for group in bench_groups:
                for iomode in self.config["iomode"]:
                    filtered = [bench for bench in group if bench in self.config["bench"]]
                    if len(filtered) > 0:
                        self._plot_sc_data_matplotlib(media, filtered, iomode, gen_dat, plot)

        # self._plot_footer()
        # self.out.close()
        # self._gen_pdf(self.out_file)

    def plot_util(self, ncore, out_dir):
        self.out_dir  = out_dir
        subprocess.call("mkdir -p %s" % self.out_dir, shell=True)
        self.out_file = os.path.join(self.out_dir, ("util.%s.gp" % ncore))
        self.out = open(self.out_file, "w")
        self._gen_log_info()
        self._plot_header()
        for media in self.config["media"]:
            for bench in self.config["bench"]:
                for iomode in self.config["iomode"]:
                    self._plot_util_data(media, ncore, bench, iomode)
        self._plot_footer()
        self.out.close()
        self._gen_pdf(self.out_file)

    def _gen_cmpdev_for_bench(self, ncore, bench):
        # for each file system
        print("## %s" % bench, file=self.out)
        print("# fs ssd-rel hdd-rel mem ssd hdd", file=self.out)
        for fs in self._get_fs_list("*", bench):
            data = self.parser.search_data(["*", fs, bench, "%s" % ncore])
            dev_val = {}
            for d_kv in data:
                dev = d_kv[0][0]
                dev_val[dev] = d_kv[1]
            # XXX: ugly [[[
            if dev_val.get("mem", None) == None:
                print("WARNING: there is no %s:%s:%s:%s result." %
                      ("mem", fs, bench, ncore), file=sys.stderr)
                continue
            if dev_val.get("ssd", None) == None:
                print("WARNING: there is no %s:%s:%s:%s result." %
                      ("ssd", fs, bench, ncore), file=sys.stderr)
                continue
            if dev_val.get("hdd", None) == None:
                print("WARNING: there is no %s:%s:%s:%s result." %
                      ("hdd", fs, bench, ncore), file=sys.stderr)
                continue
            # fs ssd-rel hdd-rel mem ssd hdd 
            mem_perf = float(dev_val["mem"]["works/sec"])
            ssd_perf = float(dev_val["ssd"]["works/sec"])
            hdd_perf = float(dev_val["hdd"]["works/sec"])
            print("%s %s %s %s %s %s" %
                  (fs,
                   ssd_perf/mem_perf, hdd_perf/mem_perf,
                   mem_perf, ssd_perf, hdd_perf),
                  file=self.out)
            # XXX: ugly ]]]
        print("\n", file=self.out)

    def gen_cmpdev(self, ncore, out_dir):
        self.out_dir  = out_dir
        subprocess.call("mkdir -p %s" % self.out_dir, shell=True)
        self.out_file = os.path.join(self.out_dir, ("cmpdev.%s.dat" % ncore))
        self.out = open(self.out_file, "w")
        ## TC
        # fs ssd-rel hdd-rel mem ssd hdd
        for bench in self.config["bench"]:
            self._gen_cmpdev_for_bench(ncore, bench)
        self.out.close()

def __print_usage():
    print("Usage: plotter.py --log [log file] ")
    print("                  --gp [gnuplot output]")
    print("                  --ty [sc | util]")
    print("                  --ncore [# core (only for util)]")

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("--log",   help="Log file")
    parser.add_option("--ty",    help="{sc | util | cmpdev }")
    parser.add_option("--out",   help="output directory")
    parser.add_option("--ncore", help="# core (only for utilization and cmpdev)", default="1")
    (opts, args) = parser.parse_args()

    # check arg
    for opt in vars(opts):
        val = getattr(opts, opt)
        if val == None:
            print("Missing options: %s" % opt)
            parser.print_help()
            exit(1)
    # run
    plotter = Plotter(opts.log)
    if opts.ty == "sc":
        plotter.plot_sc(opts.out)
    elif "sc-matplotlib" in opts.ty:
        gen_dat = "gen" in opts.ty
        plot = "plotter" in opts.ty
        if not gen_dat and not plot: # legacy
            gen_dat = True
            plot = True
        print("gen_dat:" + str(gen_dat) + ", plot:" + str(plot))
        plotter.plot_sc_matplotlib(opts.out, gen_dat, plot)
    elif opts.ty == "util":
        plotter.plot_util(int(opts.ncore), opts.out)
    elif opts.ty == "cmpdev":
        plotter.gen_cmpdev(int(opts.ncore), opts.out)
    else:
        __print_usage()
        exit(1)
