# Runtime launch package

This package declares only the three outer VMs used to run Cinder Typhoon. The
maintained scenario, container topology, challenge content, and accepted product
behavior remain under `cinder-typhoon/` in this private repository.

Register the three source names and exact source versions in BigRAE's image
registry. Each registry entry must name the matching immutable private GCE
custom image. The pack does not choose cloud images, and the adapter does not
provision infrastructure.

Training and KeplerOps use BigRAE's existing `preconfigured-machine-host`
contract. Their image-owned first-boot services create fresh Docker volumes and
bring up their participant RDP containers. ARWC is a backend-only exact custom
image.

The adapter exchanges the KeplerOps and ARWC public CA certificates over the
range's private network, gives KeplerOps the allocated ARWC private address,
restarts the two existing connectors, and verifies all three image-owned
services. It does not select images, create networks, manage credentials, or
replace BigRAE lifecycle and access behavior.
