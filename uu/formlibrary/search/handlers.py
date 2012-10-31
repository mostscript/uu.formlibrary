from uu.retrieval.catalog import SimpleCatalog


def handle_multiform_modify(context, event):
    """Will add or replace catalof for a multiform"""
    context.catalog = SimpleCatalog(context)
    for uid, record in context.items():
        context.catalog.index(record)


def handle_multiform_savedata(context):
    """Hook called from update() of multiform entry view/form"""
    handle_multiform_modify(context, None)  # for now, just replace catalog

