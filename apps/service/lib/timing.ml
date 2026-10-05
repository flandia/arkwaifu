(** Request-local timings; database time includes SQLite worker scheduling. *)

open Lwt.Infix

type t = { mutable pool : float; mutable database : float; mutable json : float }

let current = Lwt.new_key ()
let now = Unix.gettimeofday
let elapsed start = max 0. ((now () -. start) *. 1000.)

let add_pool milliseconds =
  Option.iter (fun timing -> timing.pool <- timing.pool +. milliseconds)
    (Lwt.get current)

let database callback =
  let start = now () in
  Lwt.finalize callback (fun () ->
      Option.iter
        (fun timing -> timing.database <- timing.database +. elapsed start)
        (Lwt.get current);
      Lwt.return_unit)

let json callback =
  let start = now () in
  Fun.protect callback ~finally:(fun () ->
      Option.iter (fun timing -> timing.json <- timing.json +. elapsed start)
        (Lwt.get current))

let middleware handler request =
  let timing = { pool = 0.; database = 0.; json = 0. } in
  let start = now () in
  let path, _ = Dream.split_target (Dream.target request) in
  Lwt.with_value current (Some timing) (fun () ->
      handler request >|= fun response ->
      Dream.set_header response "Server-Timing"
        (Printf.sprintf "pool;dur=%.3f, db;dur=%.3f, json;dur=%.3f"
           timing.pool timing.database timing.json);
      Dream.log
        "request timing path=%S status=%d total_ms=%.3f pool_ms=%.3f db_ms=%.3f json_ms=%.3f"
        path (Dream.status response |> Dream.status_to_int)
        (elapsed start) timing.pool timing.database timing.json;
      response)
