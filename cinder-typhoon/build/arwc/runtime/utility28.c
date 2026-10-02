#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <sys/un.h>
#include <unistd.h>

#ifndef TEXT_PAD_BYTES
#define TEXT_PAD_BYTES 1
#endif

#define FRAME_MAX 384U
#define PAYLOAD_BYTES 192U
#define ALIGNMENT_BYTES 8U
#define CANARY_OFFSET 200U
#define SAVED_RBP_OFFSET 208U
#define SAVED_RETURN_OFFSET 216U
#define CHAIN_OFFSET 224U
#define VDSO_BASE UINT64_C(0x7fff00000000)
#define VDSO_SETRESUID_OFFSET UINT64_C(0x7b0)

extern char __executable_start;

__attribute__((visibility("default"), used))
const char immutable_issuer_record[] = "ISSUER-UTIL-OG2-R4";

__attribute__((visibility("default"), used))
char request_correlation[37] = {0};

__attribute__((visibility("default"), naked, used))
void gadget_pop_rdi(void) { __asm__("pop %rdi; ret"); }

__attribute__((visibility("default"), naked, used))
void gadget_pop_rsi(void) { __asm__("pop %rsi; ret"); }

__attribute__((visibility("default"), naked, used))
void gadget_pop_rdx(void) { __asm__("pop %rdx; ret"); }

__attribute__((visibility("default"), naked, used))
void gadget_stack_pivot(void) { __asm__("leave; ret"); }

__attribute__((visibility("default"), naked, used))
void controlled_target(void) { __asm__("ret"); }

__attribute__((visibility("default"), noinline, used))
void ordinary_return(void) { __asm__ volatile("" ::: "memory"); }

__attribute__((used, section(".text.contract"), aligned(1)))
const unsigned char contract_text_pad[TEXT_PAD_BYTES] = {
    [0 ... TEXT_PAD_BYTES - 1] = 0x90
};

static uint64_t load_u64(const unsigned char *value) {
    uint64_t result;
    memcpy(&result, value, sizeof(result));
    return result;
}

static int parse_u64(const char *name, uint64_t *value) {
    const char *text = getenv(name);
    char *end = NULL;
    if (text == NULL || *text == '\0') return -1;
    errno = 0;
    *value = strtoull(text, &end, 16);
    return errno == 0 && end != text && *end == '\0' ? 0 : -1;
}

static int uuid_text(const char *value) {
    if (value == NULL || strlen(value) != 36) return 0;
    for (size_t index = 0; index < 36; ++index) {
        if (index == 8 || index == 13 || index == 18 || index == 23) {
            if (value[index] != '-') return 0;
        } else if (!((value[index] >= '0' && value[index] <= '9') ||
                     (value[index] >= 'a' && value[index] <= 'f'))) {
            return 0;
        }
    }
    return 1;
}

static int install_issuer_filter(void) {
#define ALLOW_SYSCALL(number) \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (number), 0, 1), \
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        ALLOW_SYSCALL(__NR_setresuid),
        ALLOW_SYSCALL(__NR_getuid),
        ALLOW_SYSCALL(__NR_geteuid),
        ALLOW_SYSCALL(__NR_socket),
        ALLOW_SYSCALL(__NR_connect),
        ALLOW_SYSCALL(__NR_read),
        ALLOW_SYSCALL(__NR_write),
        ALLOW_SYSCALL(__NR_close),
        ALLOW_SYSCALL(__NR_exit),
        ALLOW_SYSCALL(__NR_exit_group),
        ALLOW_SYSCALL(__NR_rt_sigreturn),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA)),
    };
    const struct sock_fprog program = {
        .len = (unsigned short)(sizeof(filter) / sizeof(filter[0])),
        .filter = filter,
    };
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) return -1;
    return prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program);
#undef ALLOW_SYSCALL
}

__attribute__((visibility("default"), noinline, used))
int issue_client(const char *issuer, const char *correlation) {
    static const char socket_path[] = "/run/arwc/control-issuer.sock";
    char request[512];
    char response[4096];
    struct sockaddr_un address;
    int descriptor;
    int request_length;
    ssize_t received;

    if (issuer != immutable_issuer_record || correlation != request_correlation ||
            !uuid_text(correlation)) return 72;
    request_length = snprintf(
        request, sizeof(request),
        "{\"issuer_record\":\"%s\",\"correlation\":\"%s\","
        "\"outlet_group\":\"OG-CRR-02\",\"project\":\"CRR-CTRL-R21\","
        "\"actions\":[\"plan-execute\",\"readback\"]}\n",
        issuer, correlation);
    if (request_length < 1 || (size_t)request_length >= sizeof(request)) return 73;
    if (install_issuer_filter() != 0) return 74;
    if (setresuid(0, 0, 0) != 0 || getuid() != 0 || geteuid() != 0) return 75;
    descriptor = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (descriptor < 0) return 76;
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
    memcpy(address.sun_path, socket_path, sizeof(socket_path));
    if (connect(descriptor, (struct sockaddr *)&address, sizeof(address)) != 0) return 77;
    if (write(descriptor, request, (size_t)request_length) != request_length) return 78;
    received = read(descriptor, response, sizeof(response) - 1);
    if (received < 1) return 79;
    response[received] = '\0';
    close(descriptor);
    if (write(STDOUT_FILENO, response, (size_t)received) != received) return 80;
    return 0;
}

static int use_client(void) {
    static const char socket_path[] = "/run/arwc/control-issuer.sock";
    const char *token = getenv("ARWC_W28_CONTROL_CLIENT");
    char request[768];
    char response[4096];
    struct sockaddr_un address;
    int descriptor;
    int request_length;
    ssize_t received;
    if (token == NULL || strlen(token) < 20 || strlen(token) > 256) return 81;
    request_length = snprintf(
        request, sizeof(request),
        "{\"operation\":\"readback\",\"control_client\":\"%s\","
        "\"outlet_group\":\"OG-CRR-02\",\"project\":\"CRR-CTRL-R21\","
        "\"action\":\"readback\"}\n", token);
    if (request_length < 1 || (size_t)request_length >= sizeof(request)) return 82;
    if (install_issuer_filter() != 0) return 83;
    descriptor = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (descriptor < 0) return 84;
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
    memcpy(address.sun_path, socket_path, sizeof(socket_path));
    if (connect(descriptor, (struct sockaddr *)&address, sizeof(address)) != 0) return 85;
    if (write(descriptor, request, (size_t)request_length) != request_length) return 86;
    received = read(descriptor, response, sizeof(response) - 1);
    if (received < 1) return 87;
    response[received] = '\0';
    close(descriptor);
    if (write(STDOUT_FILENO, response, (size_t)received) != received) return 88;
    return 0;
}

static int frame_valid(const unsigned char *frame, size_t length, int issue,
                       uint64_t canary, uint64_t base) {
    const uintptr_t runtime_base = (uintptr_t)&__executable_start;
    const uint64_t pop_rdi = base + ((uintptr_t)&gadget_pop_rdi - runtime_base);
    const uint64_t pop_rsi = base + ((uintptr_t)&gadget_pop_rsi - runtime_base);
    const uint64_t pop_rdx = base + ((uintptr_t)&gadget_pop_rdx - runtime_base);
    const uint64_t pivot = base + ((uintptr_t)&gadget_stack_pivot - runtime_base);
    const uint64_t controlled = base + ((uintptr_t)&controlled_target - runtime_base);
    const uint64_t issuer = base + ((uintptr_t)&immutable_issuer_record - runtime_base);
    const uint64_t correlation = base + ((uintptr_t)&request_correlation - runtime_base);
    const uint64_t issuer_call = base + ((uintptr_t)&issue_client - runtime_base);
    const uint64_t vdso_setresuid = VDSO_BASE + VDSO_SETRESUID_OFFSET;

    if (length > FRAME_MAX || length < CHAIN_OFFSET + 16 ||
            load_u64(frame + CANARY_OFFSET) != canary ||
            load_u64(frame + SAVED_RBP_OFFSET) != base + CHAIN_OFFSET ||
            load_u64(frame + SAVED_RETURN_OFFSET) != pivot) return 0;

    const uint64_t *chain = (const uint64_t *)(const void *)(frame + CHAIN_OFFSET);
    if (!issue) {
        return length == CHAIN_OFFSET + 16 && chain[0] == pop_rdi &&
               chain[1] == controlled;
    }
    if (length != CHAIN_OFFSET + 12 * sizeof(uint64_t)) return 0;
    return chain[0] == pop_rdi && chain[1] == 0 &&
           chain[2] == pop_rsi && chain[3] == 0 &&
           chain[4] == pop_rdx && chain[5] == 0 &&
           chain[6] == vdso_setresuid && chain[7] == pop_rdi &&
           chain[8] == issuer && chain[9] == pop_rsi &&
           chain[10] == correlation && chain[11] == issuer_call;
}

static int control_mode(int issue) {
    unsigned char frame[FRAME_MAX];
    uint64_t canary, base;
    const char *correlation = getenv("ARWC_W28_CORRELATION");
    const char *length_text = getenv("ARWC_W28_LENGTH");
    char *end = NULL;
    unsigned long requested;
    size_t consumed = 0;

    if (parse_u64("ARWC_W28_CANARY", &canary) != 0 ||
            parse_u64("ARWC_W28_PIE_BASE", &base) != 0 ||
            length_text == NULL) return 64;
    errno = 0;
    requested = strtoul(length_text, &end, 10);
    if (errno != 0 || end == length_text || *end != '\0' || requested > FRAME_MAX) return 65;
    while (consumed < requested) {
        ssize_t count = read(STDIN_FILENO, frame + consumed, requested - consumed);
        if (count <= 0) return 66;
        consumed += (size_t)count;
    }
    if (!frame_valid(frame, consumed, issue, canary, base)) return 67;
    if (!issue) {
        static const char accepted[] =
            "{\"controlled_flow\":true,\"frame\":\"UTIL-CRR-ISSUER-R4\"}\n";
        return write(STDOUT_FILENO, accepted, sizeof(accepted) - 1) ==
               (ssize_t)(sizeof(accepted) - 1) ? 0 : 68;
    }
    if (!uuid_text(correlation)) return 69;
    memcpy(request_correlation, correlation, sizeof(request_correlation));
    return issue_client(immutable_issuer_record, request_correlation);
}

static int ordinary(const char *name) {
    static const struct {
        const char *name;
        const char *result;
    } cases[] = {
        {"status", "ready"}, {"dry-readback", "bounded"},
        {"revision", "R4"}, {"relation", "REL-UTIL-ISSUER-4"},
        {"socket-check", "fixed"},
    };
    for (size_t index = 0; index < sizeof(cases) / sizeof(cases[0]); ++index) {
        if (strcmp(name, cases[index].name) == 0) {
            printf("{\"invocation\":\"%s\",\"result\":\"%s\",\"status\":\"complete\"}\n",
                   cases[index].name, cases[index].result);
            ordinary_return();
            return 0;
        }
    }
    return 70;
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "ordinary") == 0) return ordinary(argv[2]);
    if (argc == 2 && strcmp(argv[1], "validate-flow") == 0) return control_mode(0);
    if (argc == 2 && strcmp(argv[1], "issue-client") == 0) return control_mode(1);
    if (argc == 2 && strcmp(argv[1], "use-client") == 0) return use_client();
    return 71;
}
