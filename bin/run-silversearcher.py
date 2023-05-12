#!/usr/bin/env python3
import os
import sys
import signal
import subprocess
import datetime
import tempfile
import optparse
import time
import pdb
import shutil
from os.path import join

CUR_DIR = os.path.abspath(os.path.dirname(__file__))

class SilverSearcher(object):
    WORKLOAD_DIR = os.path.normpath(os.path.join(CUR_DIR, "silversearcher-workloads"))
    PRE_SCRIPT = os.path.normpath(os.path.join(CUR_DIR, "turnoff-aslr"))
    PERF_STR = "seconds"

    def __init__(self, type_, ncore_, duration_, root_,
                 profbegin_, profend_, proflog_):
        self.config = None
        self.bench_out = None
        # take configuration parameters
        self.workload = type_
        self.ncore = int(ncore_)
        self.duration = int(duration_)
        self.root = root_
        self.profbegin = profbegin_
        self.profend = profend_
        self.proflog = proflog_
        self.profenv = ' '.join(["PERFMON_LEVEL=%s" %
                                 os.environ.get('PERFMON_LEVEL', "x"),
                                 "PERFMON_LDIR=%s"  %
                                 os.environ.get('PERFMON_LDIR',  "x"),
                                 "PERFMON_LFILE=%s" %
                                 os.environ.get('PERFMON_LFILE', "x")])
        self.perf_msg = None
        self.src = "/home/congyong/" + self.workload + "/"
        self.dst = self.root + "/" + self.workload + "/"

    def __del__(self):
        # clean up
        try:
            if self.config:
                os.unlink(self.config.name)
            if self.bench_out:
                os.unlink(self.bench_out.name)
        except:
            pass

    def run(self):
        # set up benchmark configuration
        if not self.generate_config():
            return -1
        # run pre-script then sync
        self._exec_cmd("sudo %s; sync" % SilverSearcher.PRE_SCRIPT).wait()
        # start performance profiling
        self._exec_cmd("%s %s" % (self.profenv, self.profbegin)).wait()
        # run silversearcher
        self._run_silversearcher()
        # stop performance profiling
        self._exec_cmd("%s %s" % (self.profenv, self.profend)).wait()
        return 0

    def _run_silversearcher(self):
        with tempfile.NamedTemporaryFile(delete=False) as self.bench_out:
            cmd = "sudo ag --stats-only --noaffinity --workers %d %s %s" % (self.ncore, "spinlock", self.dst) # self.dst
            p = self._exec_cmd(cmd, subprocess.PIPE)

            temp_keywords = ["matches", "searched"]
            temp_str = ""

            while True:
                for l in p.stdout.readlines():
                    self.bench_out.write("#@ ".encode("utf-8"))
                    self.bench_out.write(l)
                    l_str = str(l)
                    l_str = l_str.replace("b'", "")
                    l_str = l_str.replace("\\n'", "")
                    # print("ADD", l_str)

                    for key in temp_keywords:
                        idx = l_str.find(key)
                        if idx is not -1:
                            temp_str = temp_str + " " + l_str
                            
                    idx = l_str.find(SilverSearcher.PERF_STR)
                    if idx is not -1:
                        self.perf_msg = temp_str + " " + l_str
                # if not p.poll():
                #    break
                if self.perf_msg:
                    break
            # print(self.perf_msg)
            self.bench_out.flush()

    def report(self):
#         ERR: Error in pthread_setaffinity_np(): Invalid argument
# ERR: Performance may be affected. Use --noaffinity to suppress this message.
# ERR: Error in pthread_setaffinity_np(): Invalid argument
# ERR: Performance may be affected. Use --noaffinity to suppress this message.
# ERR: Error in pthread_setaffinity_np(): Invalid argument
# ERR: Performance may be affected. Use --noaffinity to suppress this message.
# ERR: Error in pthread_setaffinity_np(): Invalid argument
# ERR: Performance may be affected. Use --noaffinity to suppress this message.
        # 65231: 31.114: IO Summary: 34453 ops, 1148.248 ops/s, (177/177 r/w),   4.0mb/s, 420us cpu/op,   5.4ms latency
        #         0 matches
        # 0 files contained matches
        # 138 files searched
        # 26774473 bytes searched
        # 0.031542 seconds
        work = 0
        work_sec = 0

        for item in self.perf_msg.split(','):
            vk = item.strip().split()
            # print(vk)
            if vk[7] == "files" and vk[8] == "searched":
                work = vk[6]
            if vk[13] == "seconds":
                self.duration = vk[12]
            work_sec = str(int(work) / float(self.duration))
        profile_name = ""
        profile_data = ""
        try:
            with open(self.proflog, "r") as fpl:
                l = fpl.readlines()
                if len(l) >= 2:
                    profile_name = l[0]
                    profile_data = l[1]
        except:
            pass
        print("# ncpu secs works works/sec %s" % profile_name)
        print("%s %s %s %s %s" %
              (self.ncore, self.duration, work, work_sec, profile_data))

    def generate_config(self):
        print("Copy from %s to %s" % (self.src, self.dst))
        if not os.path.exists(self.dst):
            shutil.copytree(self.src, self.dst)

        return True

    def _exec_cmd(self, cmd, out=None):
        # print(cmd + ";")
        # if "silversearcher" in cmd:
        #     cmd = ":"
        p = subprocess.Popen(cmd, shell=True, stdout=out, stderr=out)
        return p

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("--type", help="workload name")
    parser.add_option("--ncore", help="number of core")
    parser.add_option("--nbg", help="not used")
    parser.add_option("--directio", help="not used")
    parser.add_option("--duration", help="benchmark time in seconds")
    parser.add_option("--root", help="benchmark root directory")
    parser.add_option("--profbegin", help="profile begin command")
    parser.add_option("--profend", help="profile end command")
    parser.add_option("--proflog", help="profile log path")
    (opts, args) = parser.parse_args()

    # print(opts)

    # check options
    for opt in vars(opts):
        val = getattr(opts, opt)
        if val == None:
            print("Missing options: %s" % opt)
            parser.print_help()
            exit(1)

    # run benchmark
    silversearcher = SilverSearcher(opts.type, opts.ncore, opts.duration, opts.root,
                          opts.profbegin, opts.profend, opts.proflog)
    rc = silversearcher.run()
    silversearcher.report()
    exit(rc)

