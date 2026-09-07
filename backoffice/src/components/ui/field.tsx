/* Re-exported from the one design system — see ./button.tsx.
 *
 * `Field` is new and is the one worth reaching for: it wires `htmlFor`, `id`,
 * `aria-describedby` and `aria-invalid` together, and puts the error under the
 * field it is about rather than in a banner above the form.
 */
export {
  Field,
  FieldError,
  Hint,
  Input,
  Label,
  Select,
  Textarea,
} from "@/ui/field"
