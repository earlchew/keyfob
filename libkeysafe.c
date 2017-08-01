#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <ctype.h>
#include <limits.h>
#include <errno.h>
#include <stdarg.h>
#include <sys/resource.h>
#include <sys/stat.h>

#define STRINGIFY(_NAME)  STRINGIFY_(_NAME)
#define STRINGIFY_(_NAME) #_NAME

#define MODULE_NAME_ STRINGIFY(MODULE_NAME)
#define MODULE_name_ STRINGIFY(MODULE_name)

static const char argIndex_[]   = "_" MODULE_NAME_ "_ARGINDEX";
static const char argFile_[]    = "_" MODULE_NAME_ "_ARGFILE";
static const char argPreload_[] = "_" MODULE_NAME_ "_PRELOAD";

static void
die(const char *aFmt, ...)
    __attribute__ ((__format__(__printf__, 1, 2), __noreturn__));

static void
die(const char *aFmt, ...)
{
    va_list argp;

    va_start(argp, aFmt);
    fprintf(stderr, MODULE_name_ ": ");
    vfprintf(stderr, aFmt, argp);
    fputc('\n', stderr);
    va_end(argp);

    _exit(1);
}

static char *
readLine_(const char *aArgFile)
{
    int rc = -1;

    char  *linebuf = 0;
    size_t bufsize = 0;

    FILE *fp = fopen(aArgFile, "r");
    if ( ! fp)
        goto out;

    ssize_t linelen = getline(&linebuf, &bufsize, fp);
    if (-1 == linelen)
        goto out;

    /* Scan the line and overwrite the terminating newline, if any.
     * This makes it simpler for the caller which can assume that
     * the returned value will not contain a delimiter. */

    for (char *cp = linebuf; *cp; ++cp)
    {
        if ('\n' == *cp)
        {
            *cp = 0;
            break;
        }
    }

    /* Purge the shared file descriptor if it can be found. This will
     * help leave the process clean of artifacts. */

    struct rlimit rlim;
    struct stat fpstat;
    if ( ! getrlimit(RLIMIT_NOFILE, &rlim)
         && ! fstat(fileno(fp), &fpstat))
    {
        for (int fd = 0; fd < rlim.rlim_cur; ++fd)
        {
            struct stat fdstat;

            if ( ! fstat(fd, &fdstat)
                 && fpstat.st_dev == fdstat.st_dev
                 && fpstat.st_ino == fdstat.st_ino)
            {
                /* There should only be one occurrence so terminate when
                 * found. This also helps reduce the amount of output
                 * when running under strace(1), etc. */

                if (fd != fileno(fp))
                {
                    close(fd);
                    break;
                }
            }
        }
    }

    rc = 0;

  out:

    if (rc)
        free(linebuf);

    if (fp)
        fclose(fp);

    return rc ? 0 : linebuf;
}

static int
replaceArg_(char **aArg, const char *aArgFile)
{
    int rc = -1;

    char *arg = readLine_(aArgFile);
    if ( ! arg)
        goto out;

    *aArg = arg;

    rc = 0;

  out:

    if (rc)
        free(arg);

    return rc;
}

static char *
strcmpenv_(const char *aEnvName, char *aEnv)
{
    char *env = 0;

    size_t namelen = strlen(aEnvName);

    if ( ! strncmp(aEnv, aEnvName, namelen) && '=' == aEnv[namelen])
        env = aEnv + namelen + 1;

    return env;
}

static int
rewritePreload_(const char *aPreload)
{
    int rc = -1;

    char *replacement = 0;

    if (aPreload)
    {
        size_t preloadlen = strlen(aPreload);

        /* LD_PRELOAD - A list of additional, user-specified, ELF shared
         * objects to be loaded before all others.  The items of the list
         * can be separated by spaces or colons.
         *
         * See handle_ld_preload():
         *  https://sourceware.org/git/?p=glibc.git;a=blob_plain;f=elf/rtld.c
         */

        static const char preloadEnv[] = "LD_PRELOAD";

        const char *preload = getenv(preloadEnv);

        if (preload)
        {
            static const char preloadSep[] = " :";

            size_t pfxlen = 0;

            for (const char *cp = preload; *cp; ++cp)
            {
                size_t namelen = strcspn(cp, preloadSep);
                if ( ! namelen)
                    continue;

                if (namelen != preloadlen || strncmp(cp, aPreload, namelen))
                {
                    pfxlen = cp - preload + namelen;
                    continue;
                }

                const char *suffix = cp + namelen;
                while (*suffix && strchr(preloadSep, *suffix))
                    ++suffix;

                size_t sfxlen = strlen(suffix);

                /* Found the inserted library, and tracked the prefix
                 * and suffix. Remove the LD_PRELOAD if this was the
                 * only inserted library, otherwise rewrite the list
                 * with this library removed. */

                size_t replacementlen = pfxlen + sfxlen;

                if ( ! replacementlen)
                    unsetenv(preloadEnv);
                else
                {
                    replacement = malloc(replacementlen + 1);
                    if ( ! replacement)
                        goto out;

                    memcpy(replacement + 0,      preload, pfxlen);
                    memcpy(replacement + pfxlen, suffix,  sfxlen);
                    replacement[replacementlen] = 0;

                    setenv(preloadEnv, replacement, 1);
                }
                break;
            }
        }
    }

    rc = 0;

  out:

    free(replacement);

    return rc;
}

static void
main_(int argc, char **argv, char **env)
{
    char *argindex   = 0;
    char *argfile    = 0;
    char *argpreload = 0;

    /* Find the parameters that match the data provided by the application.
     * These will be used to find the secret, and also find which argument
     * should be replaced. */

    for (char **envp = env; *envp; ++envp)
    {
        char *env;

        env = strcmpenv_(argIndex_, *envp);
        if (env) { argindex = env; continue; }

        env = strcmpenv_(argFile_, *envp);
        if (env) { argfile = env; continue; }

        env = strcmpenv_(argPreload_, *envp);
        if (env) { argpreload = env; continue; }
    }

    if (argindex && argfile)
    {
        char **argp = 0;

        if (isdigit((unsigned char) *argindex))
        {
            unsigned long argx   = 0;
            char         *endptr = 0;

            argx = strtoul(argindex, &endptr, 10);
            if ( ! *endptr && (ULONG_MAX != argx || ERANGE != errno)) {
                if (0 < argx && argx < argc) {
                    argp = argv + argx;
                }
            }
        }

        if ( ! argp)
            die("Unable to parse argument index - %s", argindex);

        if (replaceArg_(argp, argfile))
            die("Unable to replace argument - %s", argfile);
    }

    if (rewritePreload_(argpreload))
        die("Unable to rewrite LD_PRELOAD");

    if (argindex)
    {
        *argindex = 0;
        unsetenv(argIndex_);
    }

    if (argfile)
    {
        *argfile = 0;
        unsetenv(argFile_);
    }

    if (argpreload)
    {
        *argpreload = 0;
        unsetenv(argPreload_);
    }
}

/* http://dbp-consulting.com/tutorials/debugging/linuxProgramStartup.html */
/* https://sourceware.org/ml/libc-help/2009-11/msg00006.html */

__attribute__((__section__(".init_array")))
static void * volatile const init_ = &main_;
