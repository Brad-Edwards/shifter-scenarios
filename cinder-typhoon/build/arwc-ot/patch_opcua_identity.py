"""Apply the configured identity through asyncua's supported server setter."""
import hashlib
import pathlib

source = pathlib.Path("/workdir/core/src/drivers/plugins/python/opcua/server.py")
original = source.read_bytes()
expected = "544358a7a33fa3244dc6d4753253f17a6e7cdf01d04d5b004e16a8289c039f45"
if hashlib.sha256(original).hexdigest() != expected:
    raise SystemExit("Unrecognized OpenPLC server source; requalify the upstream patch")
text = original.decode()
unused_assignment = "            self.server.application_uri = self.config.server.application_uri\n"
initialization = "            await self.server.init()\n"
if text.count(unused_assignment) != 1 or text.count(initialization) != 1:
    raise SystemExit("OpenPLC identity patch anchors are not unique")
text = text.replace(unused_assignment, "")
text = text.replace(initialization, initialization + "            await self.server.set_application_uri(self.config.server.application_uri)\n")
source.write_text(text)
