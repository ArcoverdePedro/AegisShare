from django import template

from aegis_share.services.collaboration import file_chat_users

register = template.Library()


@register.simple_tag
def document_chat_users(file, current_user):
    return file_chat_users(file, current_user)
