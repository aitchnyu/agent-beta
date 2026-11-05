from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("djangoapp.urls")),
]

# Page views are plain Django views now (ninja hosts JSON only), so page
# 404s render the friendly page through Django's own handler.
handler404 = "djangoapp.views.errors.page_not_found"
