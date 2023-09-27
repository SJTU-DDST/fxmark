#!/usr/bin/env python3
import os
import sys
import signal
import subprocess
import optparse
import datetime
import tempfile
import pdb
import logging
from os.path import join
from perfmon import PerfMon

CUR_DIR = os.path.abspath(os.path.dirname(__file__))

try:
    import cpupol
except ImportError:
    print("No cpupolicy for this machine.")
    print("Do \'make\' at %s\n"
          % os.path.normpath(os.path.join(CUR_DIR, "..")))
    raise

def catch_ctrl_C(sig, frame):
    print("Umount a testing file system. Please wait.")

class Runner(object):
    # media path
    LOOPDEV = "/dev/loop7"
    NVMEDEV = "/dev/pmem1.3"
    HDDDEV  = "/dev/pmem1.3"
    SSDDEV  = "/dev/pmem1.3"

    # test core granularity
    CORE_FINE_GRAIN   = 0
    CORE_COARSE_GRAIN = 1

    def __init__(self, \
                 core_grain = CORE_COARSE_GRAIN, \
                 pfm_lvl = PerfMon.LEVEL_LOW, \
                 run_filter = ("*", "*", "*", "*", "*")):
        (opts, args) = parser.parse_args()

        # run config
        self.CORE_GRAIN    = core_grain
        self.PERFMON_LEVEL = pfm_lvl
        self.FILTER        = run_filter # media, fs, bench, ncore, directio
        self.DRYRUN        = False
        self.DEBUG_OUT     = False

        # bench config
        self.DISK_SIZE     = "32G"
        self.DURATION      = 30 # 30 seconds
        self.DIRECTIOS     = ["bufferedio", "directio"]  # enable directio except tmpfs -> nodirectio 
        # self.MEDIA_TYPES   = ["ssd", "hdd", "nvme", "mem"]
        self.MEDIA_TYPES   = ["nvme", "mem"]

        if opts.ty == "NOVA":
            self.FS_TYPES      = ["NOVA"]
        else:
            self.FS_TYPES      = [
                                # "NOVA",
                                "EulerFS-S",
                                # "EulerFS", 
                                # "EXT4-dax",
                                # "tmpfs", # TODO: add EXT4, EXT4-DJ

                                
            # self.FS_TYPES      = ["tmpfs",
            #                       "EXT4-dax", "ext4_no_jnl",
                                #   "xfs",
                                #   "btrfs", "f2fs",
                                # "jfs", "reiserfs", "ext2", "ext3",
            ]
        self.BENCH_TYPES   = [
            # # file
            # "DWOL",
            # "DWOM",
            # "DRBH",
            # "DRBM",
            # "DRBL",
            
            # # dir
            "MWCL", # require 30s duration to stabilize
            "MWCM",
            # "MRPL",
            # "MRPM",
            # "MRPH",
            # "MRDM",
            # "MRDL",
            # "filetest",

            # # filebench
            # "filebench_varmail",
            # "filebench_fileserver",
            # "filebench_fileserver-1k",
            # "filebench_webproxy",
            # "filebench_oltp",
            # "filebench_webserver",

            # # fio 
            # "fio_zipf_mmap", # mmap
            # "fio_zipf_sync",
            # "dbench_client",
        ]
        # self.BENCH_TYPES   = [
        #     # write/write
        #     # "DWAL",
        #     "DWOL",
        #     "DWOM",
        #     # "DWOH",
        #     # "MMAPL",
        #     # "MMAPM",
        #     # "MMAPH",
        #     # "DWSL",
        #     # "MWRL",
        #     # "MWRM",
        #     "MWCL", # require 30s duration to stabilize
        #     "MWCM",
        #     # "MWUM", # crash
        #     # "MWUL", # crash https://github.com/NVSL/linux-nova/issues/77
        #     # "DWTL",

        #     # filebench
        #     "filebench_varmail",
        #     # "filebench_oltp",
        #     "filebench_fileserver",
        #     "filebench_fileserver-1k",
        #     # "filebench_webserver",
        #     # "filebench_randomwrite",
        #     # "filebench_createfiles", # TODO: create empty files to test dir ops?
        #     "filebench_webproxy",

        #     # dbench
        #     # "dbench_client",

        #     # read/read
        #     "MRPL",
        #     "MRPM",
        #     "MRPH",

        #     "MRDM",
        #     "MRDL",
        #     "DRBH",
        #     "DRBM",
        #     "DRBL",

        #     # read/write
        #     # "MRPM_bg",
        #     # "DRBM_bg",
        #     # "MRDM_bg",
        #     # "DRBH_bg",
        #     # "DRBL_bg",
        #     # "MRDL_bg",

        #     # fio 
        #     "fio_zipf_mmap", # mmap
        #     "fio_zipf_sync",


        #     # real world
        #     # "silversearcher_kernel",

        #     # rand
        #     # "DWOM_rand",
        #     # "pagefault",
        # ]
        self.BENCH_BG_SFX   = "_bg"

        # path config
        self.ROOT_NAME      = "root"
        self.LOGD_NAME      = "../logs"
        self.FXMARK_NAME    = "fxmark"
        self.FILEBENCH_NAME = "run-filebench.py"
        self.DBENCH_NAME    = "run-dbench.py"
        self.FIO_NAME       = "run-fio.py"
        self.SILVERSEARCHER_NAME = "run-silversearcher.py"
        self.PERFMN_NAME    = "perfmon.py"

        # fs config
        self.HOWTO_MOUNT = {
            "tmpfs":self.mount_tmpfs,
            "ext2":self.mount_anyfs,
            "ext3":self.mount_anyfs,
            "EXT4-dax":self.mount_anyfs,
            "ext4_no_jnl":self.mount_ext4_no_jnl,
            "xfs":self.mount_anyfs,
            "btrfs":self.mount_anyfs,
            "f2fs":self.mount_anyfs,
            "jfs":self.mount_anyfs,
            "reiserfs":self.mount_anyfs,
            "EulerFS": self.mount_eulerfs_plain,
            "EulerFS-S": self.mount_eulerfs_master,
            "NOVA":self.mount_NOVA,
        }
        self.HOWTO_MKFS = {
            "ext2":"-F",
            "ext3":"-F",
            "EXT4-dax":"-F",
            "ext4_no_jnl":"-F",
            "xfs":"-f",
            "btrfs":"-f",
            "jfs":"-q",
            "reiserfs":"-q",
            "ext4": "-F",
        }

        # media config
        self.HOWTO_INIT_MEDIA = {
            "mem":self.init_mem_disk,
            "nvme":self.init_nvme_disk,
            "ssd":self.init_ssd_disk,
            "hdd":self.init_hdd_disk,
        }

        # misc. setup
        self.redirect    = subprocess.PIPE if not self.DEBUG_OUT else None
        self.dev_null    = open("/dev/null", "a") if not self.DEBUG_OUT else None
        self.npcpu       = cpupol.PHYSICAL_CHIPS * cpupol.CORE_PER_CHIP
        self.nhwthr      = self.npcpu * cpupol.SMT_LEVEL#,14,21,28,35,42,49,56 # 1,2,4,6,8,10,12,14,16 #1,4,8,12,16,20,24,28,32# [1,2,4,8,16,24,28,32,40,48,56] # self.get_ncores() # 1,2,4,8,16,24,28,32,40,48,56
        self.ncores = [1,2,4,8,12,16,20,24,28]
        # self.ncores = [28]
        # self.ncores      = [1,7,14,21,28,35,42,49,56] 
        # self.ncores      = [1,2,4,8,16]
        # self.ncores      = [1,4,8,12,16]
        
        self.test_root   = os.path.normpath(
            os.path.join(CUR_DIR, self.ROOT_NAME))
        self.fxmark_path = os.path.normpath(
            os.path.join(CUR_DIR, self.FXMARK_NAME))
        self.filebench_path = os.path.normpath(
            os.path.join(CUR_DIR, self.FILEBENCH_NAME))
        self.dbench_path = os.path.normpath(
            os.path.join(CUR_DIR, self.DBENCH_NAME))
        self.fio_path = os.path.normpath(
            os.path.join(CUR_DIR, self.FIO_NAME))
        self.silversearcher_path = os.path.normpath(
            os.path.join(CUR_DIR, self.SILVERSEARCHER_NAME))
        self.tmp_path = os.path.normpath(
            os.path.join(CUR_DIR, ".tmp"))
        self.disk_path = os.path.normpath(
            os.path.join(self.tmp_path, "disk.img"))
        self.perfmon_start = "%s start" % os.path.normpath(
            os.path.join(CUR_DIR, self.PERFMN_NAME))
        self.perfmon_stop = "%s stop" % os.path.normpath(
            os.path.join(CUR_DIR, self.PERFMN_NAME))
        self.perfmon_log = ""
        self.log_dir     = ""
        self.log_path    = ""
        self.umount_hook = []
        self.active_ncore = -1

    def log_start(self):
        self.log_dir = os.path.normpath(
            os.path.join(CUR_DIR, self.LOGD_NAME,
                         str(datetime.datetime.now()).replace(' ','-').replace(':','-')))
        self.log_path = os.path.normpath( os.path.join(self.log_dir, "fxmark.log"))
        self.exec_cmd("mkdir -p " + self.log_dir, self.dev_null)

        self.log_fd = open(self.log_path, "bw")
        p = self.exec_cmd("echo -n \"### SYSTEM         = \"; uname -a", self.redirect)
        if self.redirect:
            for l in p.stdout.readlines():
                self.log(l.decode("utf-8").strip())
        self.log("### DISK_SIZE      = %s"   % self.DISK_SIZE)
        self.log("### DURATION       = %ss"  % self.DURATION)
        self.log("### DIRECTIO       = %s"   % ','.join(self.DIRECTIOS))
        self.log("### MEDIA_TYPES    = %s"   % ','.join(self.MEDIA_TYPES))
        self.log("### FS_TYPES       = %s"   % ','.join(self.FS_TYPES))
        self.log("### BENCH_TYPES    = %s"   % ','.join(self.BENCH_TYPES))
        self.log("### NCORES         = %s"   % 
                 ','.join(map(lambda c: str(c), self.ncores)))
        self.log("### CORE_SEQ       = %s" % 
                 ','.join(map(lambda c: str(c), cpupol.seq_cores)))
        self.log("\n")
        self.log("### MODEL_NAME     = %s" % cpupol.MODEL_NAME)
        self.log("### PHYSICAL_CHIPS = %s" % cpupol.PHYSICAL_CHIPS)
        self.log("### CORE_PER_CHIP  = %s" % cpupol.CORE_PER_CHIP)
        self.log("### SMT_LEVEL      = %s" % cpupol.SMT_LEVEL)
        self.log("\n")

    def log_end(self):
        self.log_fd.close()

    def log(self, log):
        self.log_fd.write((log+'\n').encode('utf-8'))
        print(log)

    def get_ncores(self):
        hw_thr_cnts_map = {
            Runner.CORE_FINE_GRAIN:cpupol.test_hw_thr_cnts_fine_grain,
            Runner.CORE_COARSE_GRAIN:cpupol.test_hw_thr_cnts_coarse_grain,
        }
        ncores = []
        test_hw_thr_cnts = hw_thr_cnts_map.get(self.CORE_GRAIN,
                                               cpupol.test_hw_thr_cnts_fine_grain)
        for n in test_hw_thr_cnts:
            if n > self.npcpu:
                break
            ncores.append(n)
        return ncores

    def exec_cmd(self, cmd, out=None):
        logging.debug("EXEC: %s;" % cmd)
        # out = subprocess.PIPE
        # if "run-filebench.py" in cmd:
        #     cmd = ":"
        p = subprocess.Popen(cmd, shell=True, stdout=out, stderr=out)
        
        # with open("test.log", "wb") as f:
        # p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # for c in iter(lambda: p.stdout.read(1), b""):
            # sys.stdout.buffer.write(c)
                # f.buffer.write(c)
        p.wait()
        return p

    def keep_sudo(self):
        self.exec_cmd("sudo -v", self.dev_null)

    def drop_caches(self):
        cmd = ' '.join(["sudo", 
                        os.path.normpath(
                            os.path.join(CUR_DIR, "drop-caches"))])
        self.exec_cmd(cmd, self.dev_null)

    def set_cpus(self, ncore):
        if self.active_ncore == ncore:
            return
        self.active_ncore = ncore
        if ncore is 0:
            ncores = "all"
        else:
            ncores = ','.join(map(lambda c: str(c), cpupol.seq_cores[0:ncore]))
        cmd = ' '.join(["sudo", 
                        os.path.normpath(
                            os.path.join(CUR_DIR, "set-cpus")), 
                        ncores])
        self.exec_cmd(cmd, self.dev_null)

    def add_bg_worker_if_needed(self, bench, ncore):
        if bench.endswith(self.BENCH_BG_SFX):
            ncore = min(ncore + 1, self.nhwthr)
            return (ncore, 1)
        return (ncore, 0)

    def prepre_work(self, ncore):
        self.keep_sudo()
        self.exec_cmd("sudo sh -c \"echo 0 >/proc/sys/kernel/lock_stat\"",
                      self.dev_null)
        self.drop_caches()
        self.exec_cmd("sync", self.dev_null)
        self.set_cpus(ncore)

    def pre_work(self):
        self.keep_sudo()
        self.drop_caches()

    def post_work(self):
        self.keep_sudo()

    def unset_loopdev(self):
        self.exec_cmd(' '.join(["sudo", "losetup", "-d", Runner.LOOPDEV]),
                      self.dev_null)

    def umount(self, where):
        while True:
            p = self.exec_cmd("sudo umount " + where, self.dev_null)
            if p.returncode is not 0:
                break
        (umount_hook, self.umount_hook) = (self.umount_hook, [])
        map(lambda hook: hook(), umount_hook);

    def init_mem_disk(self):
        self.unset_loopdev()
        self.umount(self.tmp_path)
        self.unset_loopdev()
        self.exec_cmd("mkdir -p " + self.tmp_path, self.dev_null)
        if not self.mount_tmpfs("mem", "tmpfs", self.tmp_path):
            return False;
        self.exec_cmd("dd if=/dev/zero of=" 
                      + self.disk_path +  " bs=1G count=1024000",
                      self.dev_null)
        p = self.exec_cmd(' '.join(["sudo", "losetup",
                                    Runner.LOOPDEV, self.disk_path]), 
                          self.dev_null)
        if p.returncode == 0:
            self.umount_hook.append(self.deinit_mem_disk)
        return (p.returncode == 0, Runner.LOOPDEV)

    def deinit_mem_disk(self):
        self.unset_loopdev()
        self.umount(self.tmp_path)

    def init_nvme_disk(self):
        return (os.path.exists(Runner.NVMEDEV), Runner.NVMEDEV)

    def init_ssd_disk(self):
        return (os.path.exists(Runner.SSDDEV), Runner.SSDDEV)

    def init_hdd_disk(self):
        return (os.path.exists(Runner.HDDDEV), Runner.HDDDEV)

    def init_media(self, media):
        _init_media = self.HOWTO_INIT_MEDIA.get(media, None)
        if not _init_media:
            return (False, None)
        (rc, dev_path) = _init_media()
        return (rc, dev_path)

    def mount_tmpfs(self, media, fs, mnt_path):
        p = self.exec_cmd("sudo mount -t tmpfs -o mode=0777,size="
                          + self.DISK_SIZE + " none " + mnt_path,
                          self.dev_null)
        return p.returncode == 0

    def mount_anyfs(self, media, fs, mnt_path):
        (rc, dev_path) = self.init_media(media)
        if not rc:
            return False
        
        if fs == "EXT4-dax":
            fs = "ext4"

        p = self.exec_cmd("sudo mkfs." + fs
                          + " " + self.HOWTO_MKFS.get(fs, "")
                          + " " + dev_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd(' '.join(["sudo mount -t", fs, "-o dax", # for ext4
                                    dev_path, mnt_path]),
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo chmod 777 " + mnt_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        return True

    def mount_eulerfs_plain(self, media, fs, mnt_path):
        (rc, dev_path) = self.init_media(media)
        if not rc:
            return False

        p = self.exec_cmd("sudo rmmod eulerfs", self.dev_null)
        p = self.exec_cmd("sudo insmod /home/congyong/eulerfs-plain.ko", self.dev_null)
        if p.returncode is not 0:
            return False

        p = self.exec_cmd(' '.join(["sudo mount -t eulerfs", "-o init",
                                    dev_path, mnt_path]),
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo chmod 777 " + mnt_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        return True
    
    def mount_eulerfs_master(self, media, fs, mnt_path):
        (rc, dev_path) = self.init_media(media)
        if not rc:
            return False

        p = self.exec_cmd("sudo rmmod eulerfs", self.dev_null)  # if not already compiled in kernel
        p = self.exec_cmd("sudo insmod /home/congyong/eulerfs/eulerfs.ko", self.dev_null)
        if p.returncode is not 0:
            return False
        # dev_path = "/dev/pmem0" # test on dram
        p = self.exec_cmd(' '.join(["sudo mount -t eulerfs", "-o init",
                                    dev_path, mnt_path]),
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo chmod 777 " + mnt_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        return True
    
    def mount_NOVA(self, media, fs, mnt_path):
        (rc, dev_path) = self.init_media(media)
        if not rc:
            return False

        p = self.exec_cmd(' '.join(["sudo mount -t", fs, "-o init",
                                    dev_path, mnt_path]),
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo chmod 777 " + mnt_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        return True

    def mount_ext4_no_jnl(self, media, fs, mnt_path):
        (rc, dev_path) = self.init_media(media)
        if not rc:
            return False

        p = self.exec_cmd("sudo mkfs.ext4"
                          + " " + self.HOWTO_MKFS.get(fs, "")
                          + " " + dev_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo tune2fs -O ^has_journal %s" % dev_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd(' '.join(["sudo mount -t ext4",
                                    dev_path, mnt_path]),
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo chmod 777 " + mnt_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        return True

    def mount(self, media, fs, mnt_path):
        mount_fn = self.HOWTO_MOUNT.get(fs, None)
        if not mount_fn:
            return False;

        self.umount(mnt_path)
        self.exec_cmd("mkdir -p " + mnt_path, self.dev_null)
        return mount_fn(media, fs, mnt_path)

    def _match_config(self, key1, key2):
        for (k1, k2) in zip(key1, key2):
            if k1 == "*" or k2 == "*":
                continue
            if k1 != k2:
                return False
        return True

    def gen_config(self):
        for ncore in sorted(self.ncores, reverse=True):
            for bench in self.BENCH_TYPES:
                # if "fio" in bench and ncore > 16: # fio does not support > 16 cores
                #     continue

                for media in self.MEDIA_TYPES:
                    for dio in self.DIRECTIOS:
                        for fs in self.FS_TYPES:
                            mount_fn = self.HOWTO_MOUNT.get(fs, None)
                            if not mount_fn:
                                continue
                            if self._match_config(self.FILTER, \
                                                  (media, fs, bench, str(ncore), dio)):
                                # if fs == "tmpfs":
                                #     logging.warning("Setting tmpfs to mem & directio")
                                #     yield("mem", fs, bench, ncore, "directio")
                                # else:
                                if fs == "NOVA":
                                    print("# INFO: NOVA requires directio")
                                    yield(media, fs, bench, ncore, "directio")
                                elif "EulerFS" in fs:
                                    print("# INFO: EulerFS requires bufferedio")
                                    yield(media, fs, bench, ncore, "bufferedio")
                                else:
                                    yield(media, fs, bench, ncore, dio)
            print("\n\n\n")

    def fxmark_env(self):
        env = ' '.join(["PERFMON_LEVEL=%s" % self.PERFMON_LEVEL,
                        "PERFMON_LDIR=%s"  % self.log_dir,
                        "PERFMON_LFILE=%s" % self.perfmon_log])
        return env

    def get_bin_type(self, bench):
        if bench.startswith("filebench_"):
            return (self.filebench_path, bench[len("filebench_"):])
        if bench.startswith("dbench_"):
            return (self.dbench_path, bench[len("dbench_"):])
        if bench.startswith("fio_"):
            return (self.fio_path, bench[len("fio_"):])
        if bench.startswith("silversearcher_"):
            return (self.silversearcher_path, bench[len("silversearcher_"):])
        return (self.fxmark_path, bench)

    def fxmark(self, media, fs, bench, ncore, nfg, nbg, dio):
        self.perfmon_log = os.path.normpath(
            os.path.join(self.log_dir,
                         '.'.join([media, fs, bench, str(nfg), "pm"])))
        (bin, type) = self.get_bin_type(bench)
        directio = '1' if dio is "directio" else '0'
        if fs == "EXT4-dax" or fs == "ext4":
            directio = '1'

        if directio is '1':
            if fs is "tmpfs" or "EulerFS" in fs:
                print("# INFO: DirectIO under tmpfs & eulerfs disabled by default")
                directio='0';
            else: 
                print("# INFO: DirectIO Enabled")

        if "mmap" in bench and self.DURATION < 30:
            duration = 30
            print("# INFO: mmap bench requires at least 30s")
        else:
            duration = self.DURATION

        cmd = ' '.join([self.fxmark_env(),
                        bin,
                        "--type", type,
                        "--ncore", str(ncore),
                        "--nbg",  str(nbg),
                        "--duration", str(duration),
                        "--directio", directio,
                        "--root", self.test_root,
                        "--profbegin", "\"%s\"" % self.perfmon_start,
                        "--profend",   "\"%s\"" % self.perfmon_stop,
                        "--proflog", self.perfmon_log])
        p = self.exec_cmd(cmd, self.redirect)
        if self.redirect:
            for l in p.stdout.readlines():
                self.log(l.decode("utf-8").strip())

    def fxmark_cleanup(self):
        cmd = ' '.join([self.fxmark_env(),
                        "%s; rm -f %s/*.pm" % (self.perfmon_stop, self.log_dir)])
        self.exec_cmd(cmd)
        self.exec_cmd("sudo sh -c \"echo 0 >/proc/sys/kernel/lock_stat\"",
                      self.dev_null)

    def run(self):
        try:
            cnt = -1
            self.log_start()
            for (cnt, (media, fs, bench, ncore, dio)) in enumerate(self.gen_config()):
                (ncore, nbg) = self.add_bg_worker_if_needed(bench, ncore)
                nfg = ncore - nbg

                if self.DRYRUN:
                    self.log("## %s:%s:%s:%s:directio" % (media, fs, bench, nfg)) # plot directio & bufferedio together
                    continue
                self.prepre_work(ncore)
                if not self.mount(media, fs, self.test_root):
                    self.log("# Fail to mount %s on %s." % (fs, media))
                    continue
                self.log("## %s:%s:%s:%s:directio" % (media, fs, bench, nfg)) # plot directio & bufferedio together
                self.pre_work()
                self.fxmark(media, fs, bench, ncore, nfg, nbg, dio)
                self.post_work()
            self.log("### NUM_TEST_CONF  = %d" % (cnt + 1))
        finally:
            signal.signal(signal.SIGINT, catch_ctrl_C)
            self.log_end()
            self.fxmark_cleanup()
            self.umount(self.test_root)
            self.set_cpus(0)

def confirm_media_path():
    pass
    # print("%" * 80)
    # print("%% WARNING! WARNING! WARNING! WARNING! WARNING!")
    # print("%" * 80)
    # yn = input("All data in %s, %s, %s and %s will be deleted. Is it ok? [Y,N]: "
    #         % (Runner.HDDDEV, Runner.SSDDEV, Runner.NVMEDEV, Runner.LOOPDEV))
    # if yn != "Y":
    #     print("Please, check Runner.LOOPDEV and Runner.NVMEDEV")
    #     exit(1)
    # yn = input("Are you sure? [Y,N]: ")
    # if yn != "Y":
    #     print("Please, check Runner.LOOPDEV and Runner.NVMEDEV")
    #     exit(1)
    # print("%" * 80)
    # print("\n\n")

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("--ty")
    
    # config parameters
    # -----------------
    #
    # o testing core granularity
    # - Runner.CORE_FINE_GRAIN
    # - Runner.CORE_COARSE_GRAIN
    #
    # o profiling level
    # - PerfMon.LEVEL_LOW
    # - PerfMon.LEVEL_PERF_RECORD
    # - PerfMon.LEVEL_PERF_PROBE_SLEEP_LOCK
    # - PerfMon.LEVEL_PERF_PROBE_SLEEP_LOCK_D  # do NOT use if you don't understand what it is
    # - PerfMon.LEVEL_PERF_LOCK                # do NOT use if you don't understand what it is
    # - PerfMon.LEVEL_PERF_STAT                # for cycles and instructions
    #
    # o testcase filter
    # - (storage device, filesystem, test case, # core, directio | bufferedio)

    # TODO: make it scriptable
    run_config = [
        (Runner.CORE_FINE_GRAIN,
         PerfMon.LEVEL_LOW,
        #  ("mem", "tmpfs", "MWCM", "*", "directio")),
        #  ("mem", "*", "DWOL", "80", "directio")),
        # ("nvme", "*", "*", "*", "directio")),
        ("nvme", "*", "*", "*", "directio")),# NOVA requires directio, EulerFS-S requires bufferedio
        # ("mem", "tmpfs", "filebench_varmail", "32", "directio")),
        # (Runner.CORE_COARSE_GRAIN,
        #  PerfMon.LEVEL_PERF_RECORD,
        #  ("*", "*", "*", "*", "bufferedio")),
        #
        # (Runner.CORE_COARSE_GRAIN,
        #  PerfMon.LEVEL_PERF_RECORD,
        #  ("*", "*", "*", str(cpupol.PHYSICAL_CHIPS * cpupol.CORE_PER_CHIP), "*"))
    ]

    # set logging level to debug
    # logging.basicConfig(level=logging.DEBUG)

    confirm_media_path()
    for c in run_config:
        runner = Runner(c[0], c[1], c[2])
        runner.run()
