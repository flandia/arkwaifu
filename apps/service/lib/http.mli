(** Build all HTTP routes over one live database reader. *)
val routes : database:Database.t -> object_base_url:string -> Dream.handler
