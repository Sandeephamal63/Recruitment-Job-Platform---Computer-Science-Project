import { Controller, type Control, type FieldPath, type FieldValues } from 'react-hook-form'
import { TextField, type TextFieldProps } from '@mui/material'

type FormTextFieldProps<T extends FieldValues> = Omit<TextFieldProps, 'name' | 'value' | 'onChange'> & {
  name: FieldPath<T>
  control: Control<T>
}

export default function FormTextField<T extends FieldValues>({
  name,
  control,
  disabled,
  helperText,
  ...textFieldProps
}: FormTextFieldProps<T>) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => (
        <TextField
          {...textFieldProps}
          {...field}
          value={field.value ?? ''}
          disabled={disabled}
          error={fieldState.invalid}
          helperText={fieldState.error?.message ?? helperText}
          fullWidth
        />
      )}
    />
  )
}