
Put the following Python code in a cell to load styles:

```python
def css_styling():
    from IPython.core.display import HTML
    styles = open("../styles/custom.css", "r").read()
    return HTML(styles)

css_styling()

```
