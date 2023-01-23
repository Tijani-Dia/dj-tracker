from functools import wraps


class FieldDescriptor:
    __slots__ = ("descriptor", "attname")

    def __init__(self, descriptor, attname):
        self.descriptor = descriptor
        self.attname = attname

    def __get__(self, instance, cls):
        if instance is None:
            return self.descriptor

        if instance_tracker := getattr(instance, "_tracker", None):
            instance_tracker.get_field_tracker(self.attname).get += 1

        return self.descriptor.__get__(instance, cls)


class DeferredAttributeDescriptor(FieldDescriptor):
    __slots__ = ()

    def __init__(self, descriptor, attname):
        super().__init__(descriptor, attname)
        descriptor._check_parent_chain = self.wrap_check_parent_chain(
            descriptor._check_parent_chain, attname
        )

    @staticmethod
    def wrap_check_parent_chain(_check_parent_chain, attname):
        @wraps(_check_parent_chain)
        def wrapper(instance):
            value = _check_parent_chain(instance)
            if value is None and (
                instance_tracker := getattr(instance, "_tracker", None)
            ):
                instance_tracker.queryset.add_deferred_field(attname, instance)

            return value

        return wrapper

    def __set__(self, instance, value):
        instance.__dict__[self.attname] = value
        if instance_tracker := getattr(instance, "_tracker", None):
            instance_tracker.get_field_tracker(self.attname).set += 1

    def __delete__(self, instance):
        del instance.__dict__[self.attname]


class EditableFieldDescriptor(FieldDescriptor):
    __slots__ = ()

    def __set__(self, instance, value):
        self.descriptor.__set__(instance, value)
        if instance_tracker := getattr(instance, "_tracker", None):
            instance_tracker.get_field_tracker(self.attname).set += 1


class SingleRelationDescriptor(EditableFieldDescriptor):
    __slots__ = ()

    def __init__(self, descriptor, attname):
        super().__init__(descriptor, attname)
        if get_queryset := getattr(descriptor, "get_queryset", None):
            descriptor.get_queryset = self.wrap_get_queryset(get_queryset, attname)

    @staticmethod
    def wrap_get_queryset(get_queryset, attname):
        @wraps(get_queryset)
        def wrapper(**hints):
            return get_queryset(**hints, field=attname)

        return wrapper


class MultipleRelationDescriptor(FieldDescriptor):
    __slots__ = ()

    def __init__(self, descriptor, attname):
        super().__init__(descriptor, attname)
        descriptor.related_manager_cls._apply_rel_filters = self.wrap_apply_rel_filters(
            descriptor.related_manager_cls._apply_rel_filters, attname
        )

    @staticmethod
    def wrap_apply_rel_filters(_apply_rel_filters, attname):
        @wraps(_apply_rel_filters)
        def wrapper(manager, queryset):
            queryset._add_hints(field=attname)
            return _apply_rel_filters(manager, queryset)

        return wrapper

    def __set__(self, instance, value):
        return self.descriptor.__set__(instance, value)


DESCRIPTORS_MAP = {
    "DeferredAttribute": DeferredAttributeDescriptor,
    "ForeignKeyDeferredAttribute": EditableFieldDescriptor,
    "GenericForeignKey": SingleRelationDescriptor,
    "ForwardManyToOneDescriptor": SingleRelationDescriptor,
    "ForwardOneToOneDescriptor": SingleRelationDescriptor,
    "ReverseOneToOneDescriptor": SingleRelationDescriptor,
    "ManyToManyDescriptor": MultipleRelationDescriptor,
    "ReverseManyToOneDescriptor": MultipleRelationDescriptor,
    "ReverseGenericManyToOneDescriptor": MultipleRelationDescriptor,
}
