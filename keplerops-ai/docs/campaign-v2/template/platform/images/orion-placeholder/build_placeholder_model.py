from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


OUTPUT = Path("/models/orion-placeholder.onnx")
FEATURE_COUNT = 16
CLASS_COUNT = 8


def main() -> None:
    input_tensor = helper.make_tensor_value_info(
        "features", TensorProto.FLOAT, [None, FEATURE_COUNT]
    )
    output_tensor = helper.make_tensor_value_info(
        "probabilities", TensorProto.FLOAT, [None, CLASS_COUNT]
    )
    weights = numpy_helper.from_array(
        np.zeros((FEATURE_COUNT, CLASS_COUNT), dtype=np.float32), name="weights"
    )
    bias = numpy_helper.from_array(
        np.zeros((CLASS_COUNT,), dtype=np.float32), name="bias"
    )
    graph = helper.make_graph(
        [
            helper.make_node(
                "Gemm", ["features", "weights", "bias"], ["logits"]
            ),
            helper.make_node("Softmax", ["logits"], ["probabilities"], axis=1),
        ],
        "orion-neutral-placeholder",
        [input_tensor],
        [output_tensor],
        [weights, bias],
    )
    model = helper.make_model(
        graph,
        producer_name="keplerops-clean-platform",
        opset_imports=[helper.make_opsetid("", 18)],
    )
    model.ir_version = 10
    onnx.checker.check_model(model)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, OUTPUT)


if __name__ == "__main__":
    main()
