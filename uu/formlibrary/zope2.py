
def initialize(context):
    """make this a Zope2 product package"""
    import patch  # noqa - monkey patches PAS cookie handler unauthorized
