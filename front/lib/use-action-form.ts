"use client";

import {
  type FormEvent,
  startTransition,
  useActionState,
  useEffect,
  useState,
} from "react";
import { type FormState, IDLE } from "./action-state";

type Action = (previous: FormState, formData: FormData) => Promise<FormState>;

/**
 * Wires a server action to a form without React's automatic form reset, so a refused
 * submission (409, 422) keeps what the person typed. After a successful one `formKey`
 * changes: put it on the `<form>` and the fields start empty again.
 */
export function useActionForm(action: Action) {
  const [state, dispatch, pending] = useActionState(action, IDLE);
  const [formKey, setFormKey] = useState(0);

  useEffect(() => {
    if (state.status === "ok") setFormKey((key) => key + 1);
  }, [state]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // The submitter carries "load it anyway" (name/value) when that button was pressed.
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    const data = new FormData(event.currentTarget, submitter);
    startTransition(() => dispatch(data));
  }

  return { state, pending, formKey, onSubmit };
}
