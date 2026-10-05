(** Request-local elapsed milliseconds for the HTTP log and Server-Timing. *)

val now : unit -> float
val elapsed : float -> float
val add_pool : float -> unit
val database : (unit -> 'a Lwt.t) -> 'a Lwt.t
val json : (unit -> 'a) -> 'a
val middleware : Dream.middleware
