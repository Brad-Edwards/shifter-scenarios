# Runtime launch package

This package describes the two outer VMs used to host Polaris. The maintained
logical scenario, container topology, content and answers remain under
`polaris/` in this private repository. It does not replace that logical contract.

The outer range LAN uses allocator-owned addresses on both AWS and GCP. Neither
the directory address nor participant public key is hard-coded: the adapter
receives them through typed SDK runtime references. The container networks keep
their private authored topology inside the baked host image.

Register exact provider images for the `polaris-vm` and `polaris-dc` source
aliases. The container host management SSH service must use its baked management
port and user; participant SSH remains port 22 and its actual key is observed
through the pinned management channel. The host image must include ssh-keyscan.
The participant container image must contain the pinned model client.

Install this pack archive through tenant administration, install the separately
published adapter manifest, and bind `host` to the compiled a14-kali guest and
`directory` to the compiled dc01 guest. Assign the participant model policy and
the adapter's model parameters. Compatibility is not live qualification.
