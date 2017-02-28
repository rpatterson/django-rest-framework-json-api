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

    def to_internal_value(self, data):
        """
        Return the serializer corresponding to the resource type.
        """
        if data not in self.serializer_classes:
            raise serializers.ValidationError(
                'No serializer available for type {0!r}'.format(data))
        return self.serializer_classes[data]

    def to_representation(self, obj):
        """
        Return the resource type corresponding to the serializer.
        """
        if obj not in self.resource_types:
            raise serializers.ValidationError(
                'No resource type available for serializer {0!r}'.format(obj))
        return self.resource_types[obj]


class ResourceTypeSerializer(serializers.Serializer):
    """
    Use the `type` key to lookup a serializer to delegate the rest to.
    """

    # type = ResourceTypeSerializerField(serializer_classes=[...])

    def to_internal_value(self, data):
        """
        Capture items that aren't in our schema.
        """
        result = super(ResourceTypeSerializer, self).to_internal_value(data)

        self.type_data = {
            key: value for key, value in data.items()
            if key not in result}

        return result
    
    def validate(self, data):
        """
        Validate the rest of the fields with the serializer.
        """
        self.serializer = data['type'](data=self.type_data)
        self.serializer.is_valid(raise_exception=True)
        return self.serializer.validated_data

    def save(self):
        """
        Delegate the rest of the fields to the looked up serializer.
        """
        assert self.serializer.validated_data, (
            'You must call `.is_valid()` before saving.')
        return self.serializer.save()
