(** Public Dream Hypertext Transfer Protocol (HTTP) routes backed by a
    {!Database.t} reader. *)

val routes :
  ?china_object_base_url:string ->
  database:Database.t ->
  object_base_url:string ->
  Dream.handler
(** [routes ?china_object_base_url ~database ~object_base_url] builds the
    health and JSON API handler.

    The handler accepts [GET] and [OPTIONS], normalizes supported locale path
    parameters to uppercase, and adds public cross-origin resource sharing
    headers to every response. It maps [`Not_found] to HTTP 404 and
    [`Unavailable _] or invalid asset metadata to HTTP 503 without
    exposing database details. [object_base_url] supplies the default public
    object prefix. When [china_object_base_url] is set, a request whose exact
    [X-Forwarded-Host] is [api.cn.arkwaifu.cc] uses that prefix instead. *)
