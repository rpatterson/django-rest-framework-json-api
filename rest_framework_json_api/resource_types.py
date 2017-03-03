"""
A field and serializer for a sort of JSON generic relations support.

The generic serializer defines a `type` field which is used to map resource
type strings to serializer classes.  Then the generic serializer will
instantiate the specific serializer class and delegate the rest to it.
"""

from rest_framework_json_api import utils
from rest_framework_json_api import serializers


class ResourceTypeSerializerField(serializers.Field):
    """
    Map JSON API resource types to serializers.
    """

    default_error_messages = {
        'resource_type': 'No serializer available for type {value!r}',
        'serializer': 'No resource type available for serializer {value!r}'}

    def __init__(
            self, serializer_classes={}, format_type=None, pluralize=None,
            **kwargs):
        """Map resource types to serializers:

        If a `urls` configuration is given, then it will be introspected to
        map resource type to the serializer class associated with that
        resource type's view.  If the resource type cannot be found in that
        mapping, then lookup will fall back to the mapping of resource types
        to serializer classes must be given in `serializer_classes`.

        """
        super(ResourceTypeSerializerField, self).__init__(**kwargs)

        assert serializer_classes, 'Must give `serializer_classes`'
        if isinstance(serializer_classes, list):
            self.serializer_classes = {
                utils.get_resource_type_from_serializer(
                    serializer_class,
                    format_type=format_type, pluralize=pluralize):
                serializer_class for serializer_class in serializer_classes}
        else:
            self.serializer_classes = serializer_classes
        self.resource_types = {
            serializer_class: resource_type
            for resource_type, serializer_class
            in self.serializer_classes.items()}
        self.serializer_classes_by_model = {
            serializer_class.Meta.model: serializer_class
            for serializer_class in self.serializer_classes.values()}

    def to_internal_value(self, data):
        """
        Return the serializer corresponding to the resource type.
        """
        if data not in self.serializer_classes:
            self.fail('resource_type', value=data)
        return self.serializer_classes[data]

    def to_representation(self, obj):
        """
        Return the resource type corresponding to the serializer.
        """
        if obj not in self.resource_types:
            self.fail('serializer', value=obj)
        return self.resource_types[obj]

    def get_attribute(self, instance):
        """
        Get the serializer corresponding to the instance's class.
        """
        return self.serializer_classes_by_model[type(instance)]


class ResourceTypeSerializer(serializers.Serializer):
    """
    Use the `type` key to lookup a serializer to delegate the rest to.
    """

    # type = ResourceTypeSerializerField(serializer_classes=[...])

    def to_internal_value(self, data):
        """
        Pass on items that aren't in our schema to the type serializer.
        """
        result = super(ResourceTypeSerializer, self).to_internal_value(data)

        # Never pass `type` on as it's just how we get the serializer for the
        # resource type to delegate to
        serializer_class = result.pop('type')

        # Include all keys already processes by our schema.
        result.update(
            (key, value) for key, value in data.items()
            if key not in self.fields)

        # Return the internal value from the serializer
        self.serializer = serializer_class(data=result, context=self.context)
        # Have to do validation here in order to be able to return the following
        self.serializer.is_valid(raise_exception=True)
        return self.serializer.validated_data

    def to_representation(self, instance):
        """
        Include items from the type serializer that aren't in our schema.
        """
        result = super(ResourceTypeSerializer, self).to_representation(instance)

        # Collect all the keys that our schema might override on the resource
        # type's serializer
        source_attrs = set([])
        for field in self.fields.values():
            source_attrs.update(field.source_attrs)

        serializer_class = self.fields['type'].get_attribute(instance)
        self.serializer = serializer_class(
            instance=instance, context=self.context)

        # Add all the keys from the resource type's serializer
        # that our schema doesn't override
        result.update(
            (key, value) for key, value in self.serializer.data.items()
            if key not in self.fields)

        return result

    def save(self):
        """
        Delegate saving to the type serializer.
        """
        assert self.serializer.validated_data, (
            'You must call `self.is_valid()` before saving.')
        return self.serializer.save()
