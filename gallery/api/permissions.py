from rest_framework.permissions import BasePermission


class HasScope(BasePermission):

    def has_permission(self, request, view):
        try:
            required_scope = view.required_scope
        except:
            return True

        if not required_scope:
            return True
        if not request.auth:
            return False
        token = request.auth
        return required_scope in token.scope.split()
