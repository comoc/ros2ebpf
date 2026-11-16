/* SPDX-License-Identifier: Apache-2.0 */
#ifndef ROS2EBPF_OFFSETS_H
#define ROS2EBPF_OFFSETS_H
#include "ros2ebpf/maps.h"

/* The ROS 2 distro this branch of ros2ebpf follows (the lyrical branch also supports
 * Rolling, see offsets.c): the distro a shim outside /opt/ros/ (the colcon install/ of a
 * source build) is taken for unless shims[].distro says otherwise, and the row the config
 * map holds before the first shim is registered. */
#ifndef ROS2EBPF_DISTRO
#define ROS2EBPF_DISTRO "lyrical"
#endif

struct offset_entry {
    const char *distro;
    const char *arch;
    __u32 name_off;          /* topic_name / service_name in every rmw handle */
    __u32 msginfo_pubseq;    /* rmw_message_info_t.publication_sequence_number */
};

/* The row for (distro, arch), NULL when the table has none. */
const struct offset_entry *offsets_lookup(const char *distro, const char *arch);
/* The <distro> of a shim path /opt/ros/<distro>/lib/librmw_implementation.so (also behind
 * /proc/<pid>/root). -1 when the path is not under /opt/ros/: a colcon install/ of a
 * source build, which ros2ebpf takes for ROS2EBPF_DISTRO (offsets_resolve_distro). */
int offsets_distro_from_path(const char *path, char *out, size_t n);
/* The distro of a shim as the process sees it (`seen_path`): <distro> under /opt/ros/,
 * ROS2EBPF_DISTRO anywhere else. Whether the table has a row for it is offsets_lookup's call. */
void offsets_resolve_distro(const char *seen_path, char *out, size_t n);
/* The distros of the table, comma separated ("lyrical, rolling"), for error messages. */
const char *offsets_supported_distros(void);
/* The ROS2EBPF_DISTRO row of this machine (uname -m): what the config map holds before the
 * first shim is registered. */
const struct offset_entry *offsets_host_default(void);
/* Fills cfg fields from an entry. */
void offsets_apply(const struct offset_entry *e, struct ros2ebpf_config *cfg);
/* Verify that the shim ELF exports the symbols we attach to. Returns 0 or -1,
 * listing the missing ones in `missing` (comma separated). */
int offsets_check_shim(const char *path, char *missing, size_t n);

#endif
