const zlib = require("zlib");

const encoded = "__MANIFEST_BASE64__";
const key = Buffer.from("__MANIFEST_KEY_HEX__", "hex");

function collectionManifest() {
  const encrypted = Buffer.from(encoded, "base64");
  const compressed = Buffer.alloc(encrypted.length);
  for (let index = 0; index < encrypted.length; index += 1) {
    compressed[index] = encrypted[index] ^ key[index % key.length];
  }
  return zlib.inflateSync(compressed).toString("utf8");
}

process.stdout.write(collectionManifest());
