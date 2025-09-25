def toggle(set_, item):
    if item in set_:
        set_.remove(item)
    else:
        set_.add(item)
