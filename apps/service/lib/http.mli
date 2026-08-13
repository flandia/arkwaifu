(** Public Dream Hypertext Transfer Protocol (HTTP) routes backed by a
    {!Database.t} reader. *)

val routes : database:Database.t -> object_base_url:string -> Dream.handler
(** [routes ~database ~object_base_url] builds the health and JSON API handler.

    The handler accepts [GET] and [OPTIONS], normalizes supported locale path
    parameters to uppercase, and adds public cross-origin resource sharing
    headers to every response. It maps [`Not_found] to HTTP 404 and
    [`Unavailable _] or invalid composition metadata to HTTP 503 without
    exposing database details. [object_base_url] supplies the public bucket or
    content delivery network prefix for object URLs in JSON responses. *)
