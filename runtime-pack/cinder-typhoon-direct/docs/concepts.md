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
bring up their participant RDP containers.

ARWC uses BigRAE's existing SSH participant access. The image confines that
login to the FieldLink connector workstation. The participant does not receive
an ARWC host shell or Docker authority.

The adapter copies BigRAE's host-side password verifiers into the two RDP
containers without handling plaintext. It also exchanges the KeplerOps and
ARWC public CA certificates over the range's private network. It gives
KeplerOps the allocated ARWC private address, restarts the two existing
connectors, and verifies all three image-owned services. It does not select
images, create networks, mint credentials, or replace BigRAE lifecycle and
access behavior.
