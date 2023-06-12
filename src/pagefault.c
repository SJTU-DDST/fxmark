// SPDX-License-Identifier: MIT
/**
 * Nanobenchmark: META
 *   MU. PROCESS = {overwrite a non-overlapping region of /test/test.file}
 *       - TEST: concurrent inode.mtime  update
 */	      
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#define __STDC_FORMAT_MACROS
#include <inttypes.h>
#include <stdlib.h>
#include <assert.h>
#include "fxmark.h"
#include "util.h"

#define PRIVATE_REGION_SIZE (1024 * 1024 * 8)
// #define PRIVATE_REGION_SIZE (1024 * 1024 * 1024 * 4)
#define PRIVATE_REGION_PAGE_NUM (PRIVATE_REGION_SIZE/PAGE_SIZE)

static void set_shared_test_root(struct worker *worker, char *test_root)
{
        struct fx_opt *fx_opt = fx_opt_worker(worker);
        sprintf(test_root, "%s", fx_opt->root);
}

static void set_test_file(struct worker *worker, char *test_root)
{
        struct fx_opt *fx_opt = fx_opt_worker(worker);
        sprintf(test_root, "%s/n_mtime_upt.dat", fx_opt->root);
}

static int pre_work(struct worker *worker)
{
        char *page = NULL;
        struct bench *bench = worker->bench;
        char path[PATH_MAX];
        int fd, max_id = -1, rc;
        int i, j;

        /* allocate data buffer aligned with pagesize*/
        if(posix_memalign((void **)&(worker->page), PAGE_SIZE, PAGE_SIZE))
                goto err_out;
        page = worker->page;
        if (!page)
                goto err_out;

#if DEBUG
        /*to debug*/
        fprintf(stderr, "DEBUG: worker->id[%d], page address :%p\n",worker->id, page);
#endif
        /* a leader takes over all pre_work() */
        if (worker->id != 0)
                return 0;

        /* find the largest worker id */
        for (i = 0; i < bench->ncpu; ++i) {
                struct worker *w = &bench->workers[i];
                if (w->id > max_id)
                        max_id = w->id;
        }

        /* create a test file */
        set_shared_test_root(worker, path);
        rc = mkdir_p(path);
        if (rc) return rc;

        set_test_file(worker, path);
        if ((fd = open(path, O_CREAT | O_RDWR, S_IRWXU)) == -1)
                goto err_out;

        /* set flag with O_DIRECT if necessary*/
        if(bench->directio && (fcntl(fd, F_SETFL, O_DIRECT) == -1))
                goto err_out;

        for (i = 0; i <= max_id; ++i) {
                for (j = 0; j < PRIVATE_REGION_PAGE_NUM; ++j) {
                        if (write(fd, page, PAGE_SIZE) != PAGE_SIZE)
                                goto err_out;
                }
        }

        fsync(fd);
        close(fd);
out:
        return rc;
err_out:
        bench->stop = 1;
        rc = errno;
        if(page)
                free(page);
        goto out;
}

static void shuffle(int arr[], int n) {
    int i;
    for(i = n-1; i >= 1; i--) {
        int j = rand() % (i+1);
        int temp = arr[i];
        arr[i] = arr[j];
        arr[j] = temp;
    }
}

static int main_work(struct worker *worker)
{
        struct bench *bench = worker->bench;
        char path[PATH_MAX];
        char *page = worker->page;
        int fd, rc = 0;
        off_t pos;
        uint64_t iter = 0;

        int n = PRIVATE_REGION_PAGE_NUM; // example size of permutation
        int arr[n];
        int i;

        // FILE *log_fp;

        char *ptr;
        char buf;

        // initialize array with 1 to N
        for(i = 0; i < n; i++) {
                arr[i] = i; // +1
        }
        // seed the random number generator with current time
        srand(time(NULL));

        // shuffle the array
        shuffle(arr, n);
#if DEBUG 
        fprintf(stderr, "DEBUG: worker->id[%d], main worker address :%p\n",
                        worker->id, worker->page);
#endif

        assert(page);

        set_test_file(worker, path);
        if ((fd = open(path, O_CREAT|O_RDWR , S_IRWXU)) == -1)
                goto err_out;

        // append
        // if ((log_fd = open("/home/congyong/eulerfs/log.txt", O_CREAT|O_RDWR|O_APPEND , S_IRWXU)) == -1)
        //         goto err_out;
        // log_fp = fopen("/home/congyong/eulerfs/log.txt", "a");

        /* set flag with O_DIRECT if necessary*/
        if(bench->directio && (fcntl(fd, F_SETFL, O_DIRECT)==-1))
                goto err_out;

        pos = PRIVATE_REGION_SIZE * worker->id;
        ptr = mmap(NULL, PRIVATE_REGION_SIZE, PROT_READ, MAP_SHARED, fd, pos);

        // fprintf(log_fp, "worker %d, ptr %p\n", worker->id, ptr); (PRIVATE_REGION_SIZE/PAGE_SIZE)
        // fprintf(log_fp, "PRIVATE_REGION_SIZE=%d PAGE_SIZE=%d n=%d\n", PRIVATE_REGION_SIZE, PAGE_SIZE, n);

        for (iter = 0; !bench->stop; ++iter) { //  && iter < n
                // if (pwrite(fd, page, PAGE_SIZE, pos + arr[iter % n] * PAGE_SIZE) != PAGE_SIZE) // Old DWOM: each worker writes to its own region's same offset, may be CPU cached
                        // goto err_out;
                buf = ptr[arr[iter % n] * PAGE_SIZE];
                if (iter % n == n - 1) {
                        msync(ptr, PRIVATE_REGION_SIZE, MS_SYNC);
                }
        }

        // fprintf(log_fp, "worker %d, iter %lu\n", worker->id, iter);
        close(fd);
        // fclose(log_fp);
out:
        worker->works = (double)iter;
        return rc;
err_out:
        bench->stop = 1;
        rc = errno;
        free(page);
        goto out;
}

struct bench_operations n_pagefault_ops = {
        .pre_work  = pre_work, 
        .main_work = main_work,
};
