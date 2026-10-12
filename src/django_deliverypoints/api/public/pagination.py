# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from rest_framework.pagination import PageNumberPagination


class PublicPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 2000  # map zoom-out fetches the whole point base in one request (1k+ dealers, with headroom)
    page_query_param = "page"
