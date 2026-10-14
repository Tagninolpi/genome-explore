def merge_structure(model, d):
    for key, value in d.items():
        if isinstance(value, dict):
            if key in model:
                sub = model[key]
            else:
                sub = {}
                model[key] = sub
            if not isinstance(sub, dict):  # model has a leaf here, new value is a dict
                raise TypeError(f"Conflict on key {key!r}")
            merge_structure(sub, value)
        else:
            t = type(value).__name__
            existing = model.get(key)
            if existing is None:
                model[key] = {t}  # set of types seen for this leaf
            elif isinstance(existing, set):
                existing.add(t)
            else:  # model has a dict here, new value is a leaf
                raise TypeError(f"Conflict on key {key!r}")
    return model


def build_model(dicts):
    model = {}
    for d in dicts:
        merge_structure(model, d)
    return model

def compact(model, indent=0, step=2):
    pad = " " * indent
    lines = []
    items = list(model.items())
    for i, (key, value) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if isinstance(value, dict):
            lines.append(f"{pad}{key}: {{")
            lines.extend(compact(value, indent + step, step))
            lines.append(f"{pad}}}{comma}")
        else:
            lines.append(f"{pad}{key}{comma}")
    return lines

def get_data_model_simplified(data):
    return "{\n" + "\n".join(compact(build_model(data), indent=2)) + "\n}"
