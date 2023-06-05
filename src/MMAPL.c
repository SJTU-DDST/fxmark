// SPDX-License-Identifier: MIT
/**
 * Nanobenchmark: MMAPL
 *   RF. PROCESS = {mmap and munmap private file}
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

#define MAP_DAXVM               0x400000       

static void set_test_root(struct worker *worker, char *test_root)
{
        struct fx_opt *fx_opt = fx_opt_worker(worker);
        sprintf(test_root, "%s/%d", fx_opt->root, worker->id);
}

static int pre_work(struct worker *worker)
{
        char *page=NULL;
        struct bench *bench = worker->bench;
        char test_root[PATH_MAX];
        char file[PATH_MAX];
        int fd=-1, rc = 0;

        /* allocate data buffer aligned with pagesize*/
        if(posix_memalign((void **)&(worker->page), PAGE_SIZE, PAGE_SIZE))
                goto err_out;
        page = worker->page;
        if (!page)
                goto err_out;

        /* create test root */
        set_test_root(worker, test_root);
        rc = mkdir_p(test_root);
        if (rc) return rc;

        /* create a test file */
        snprintf(file, PATH_MAX, "%s/n_file_rd.dat", test_root);
        if ((fd = open(file, O_CREAT | O_RDWR, S_IRWXU)) == -1)
                goto err_out;
// printf("Thread %d: fd = %d, filename = %s, pos = %d\n", worker->id, fd, file, 0);
        /* set flag with O_DIRECT if necessary*/
        if(bench->directio && (fcntl(fd, F_SETFL, O_DIRECT) == -1))
                goto err_out;

        if (write(fd, page, PAGE_SIZE) != PAGE_SIZE)
                goto err_out;
out:
        /* put fd to worker's private */
        worker->private[0] = (uint64_t)fd;
        return rc;
err_out:
        rc = errno;
        if(page)
                free(page);
        goto out;
}

static int main_work(struct worker *worker)
{
        struct bench *bench = worker->bench;
        char *page=worker->page;
        int fd=-1, rc = 0;
        uint64_t iter = 0;

        char *ptr;
        int err;

        assert(page);

        fd = (int)worker->private[0];
        for (iter = 0; !bench->stop; ++iter) {
            // if (pread(fd, page, PAGE_SIZE, 0) != PAGE_SIZE)
                // goto err_out;
            ptr = mmap(NULL, PAGE_SIZE, PROT_READ, MAP_SHARED, fd, 0); //  | MAP_DAXVM
            if (ptr == MAP_FAILED)
                goto err_out;
            err = munmap(ptr, PAGE_SIZE);
            if (err)
                goto err_out;
        }
out:
        close(fd);
        worker->works = (double)iter;
        return rc;
err_out:
        bench->stop = 1;
        rc = errno;
        free(page);
        goto out;
}

struct bench_operations n_MMAPL_ops = {
        .pre_work  = pre_work,
        .main_work = main_work,
};
