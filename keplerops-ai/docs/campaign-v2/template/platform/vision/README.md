# Orion Synthetic Photonics Pattern Benchmark

This directory is the reproducible source for an internal synthetic
photonics-pattern privacy benchmark. It is a four-class model over generated
64-by-64 RGB patterns, not a component-inspection or field-performance model.
The committed contract freezes the architecture, class order, preprocessing,
training seed, optimizer, and score temperature. The committed data contains
128 training images, 32 held-out synthetic images (under the historical
`calibration/` directory name), and four protected benchmark samples.

Create an isolated CPU training environment and reproduce the committed model:

```bash
python3 -m venv /tmp/orion-vision
/tmp/orion-vision/bin/pip install -r requirements-train.txt
/tmp/orion-vision/bin/python generate_dataset.py --output data --replace
/tmp/orion-vision/bin/python train_export.py
```

`train_export.py` exports a digest-stable ONNX model containing the trained
weights plus fixed class, preprocessing, model, held-out evaluation, and
reference-inference metadata. The runtime image uses ONNX Runtime only; it does
not carry PyTorch or the protected images.

Run the complete local reproduction and API check from the template root:

```bash
VISION_PYTHON=/tmp/orion-vision/bin/python baseline/vision-prototype.sh
```

The baseline regenerates and compares every source image, retrains and
byte-compares the ONNX artifact, then exercises the authenticated service
contract twice to prove deterministic four-element score vectors and bounded
request evidence.

`engineering/reconcile-orion-vision-label-studio.sh` creates the private Orion
Photonics Privacy Benchmark project for authenticated Label Studio
contributors. It queries the live model once for each protected sample and
stores the request ID, source and model digests, bounded query position, model
revision, predicted class, and complete score vector with the Label Studio
prediction. `baseline/vision-label-studio.sh` verifies that record against a
fresh authenticated inference.

From the template root, reconcile and verify the enterprise workflow after the
model and Label Studio are ready:

```bash
sudo engineering/reconcile-orion-vision-label-studio.sh
baseline/vision-label-studio.sh
```

This benchmark does not claim calibrated probabilities, privacy guarantees,
model inversion, or completion of any challenge path.
