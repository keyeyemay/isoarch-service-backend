"""Reuse domain operations in draw.io sequence messages and validate references."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET


DIAGRAM = Path(__file__).resolve().parents[1] / "lr4_sequence.drawio"


def sync(path=DIAGRAM):
    tree = ET.parse(path)
    root = tree.getroot()
    pages = {page.get("id"): page for page in root.findall("diagram")}
    operations = {node.get("id"): node for node in pages["domains"].iter("object")
                  if node.get("kind") == "operation"}
    for operation in operations.values():
        match = re.match(r"(\w+)\.(\w+)\((.*?)\):", operation.get("signature", ""))
        if not match:
            raise ValueError(f"Invalid operation signature: {operation.get('id')}")
        _, method, parameters = match.groups()
        names = [parameter.split(":", 1)[0].strip().rstrip("?")
                 for parameter in parameters.split(",") if parameter.strip()]
        number = re.match(r"\d+\. ", operation.get("label", ""))
        prefix = number.group() if number else ""
        operation.set("label", f"{prefix}{method}({', '.join(names)})\n"
                      + operation.get("http", "").replace("?next=true", ""))
    sequence = {node.get("id"): node for node in pages["sequence"].iter()
                if node.get("id")}
    all_ids = {node.get("id") for node in root.iter() if node.get("id")}
    for page in pages.values():
        ids = [node.get("id") for node in page.iter() if node.get("id")]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate cell IDs in {page.get('name')}")

    calls = []
    for node in pages["sequence"].iter("object"):
        if node.get("classifierRef"):
            if node.get("classifierRef") not in all_ids:
                raise ValueError("Unknown lifeline classifier")
        reference = node.get("operationRef")
        if reference is None:
            continue
        if reference not in operations:
            raise ValueError(f"Unknown operation: {reference}")
        operation = operations[reference]
        signature = operation.get("signature")
        match = re.match(r"(\w+)\.(\w+)\(", signature or "")
        if not match:
            raise ValueError(f"Invalid signature: {signature}")
        domain, method = match.groups()
        node.set("signature", signature)
        node.set("operation", method)
        if node.get("messageSort") != "synchCall":
            continue
        if node.get("id", "").startswith("message-"):
            receiver = sequence[node.get("receiverRef")]
            if receiver.get("domain") != domain:
                raise ValueError(f"Message targets a different domain: {method}")
            calls.append(node)
            step = (int(node.get("id").split("-")[1]) - 1) // 2
            label = sequence[f"args-{step}"]
            label.set("signature", signature)
            label.set("operationRef", reference)
            label.set("operation", method)
            label.set("arguments", node.get("arguments", ""))
            label.set("label", f"{method}({node.get('arguments', '')})")
    if len(calls) != 8:
        raise ValueError(f"Expected 8 HTTP calls, got {len(calls)}")
    ET.indent(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return len(calls)


if __name__ == "__main__":
    print(f"Synced and validated {sync()} calls against domain operations.")
