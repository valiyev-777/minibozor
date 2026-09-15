/**
 * §5.2 ·4 — the description, as a small editor rather than a textarea.
 *
 * **The editor may not be able to produce what the phone cannot draw.** The
 * Android and iOS apps render this HTML with their own small renderer; a
 * table, a coloured span or an embedded video arriving in that string is not
 * a degraded paragraph, it is a blank space in the middle of a product page.
 * So the restriction is in the *schema*, not in the toolbar: what StarterKit
 * ships beyond bold, italic, the two lists and one heading is switched off
 * below, which means a paste from Word cannot smuggle it in either — ProseMirror
 * drops a node its schema does not know rather than keeping it as unknown
 * markup.
 *
 * That is also why there is no "source" view and no `insertContent` of raw
 * HTML anywhere: the only way text gets in is through the schema.
 *
 * **Plain text travels beside the HTML.** Search reads words, and
 * `<p><strong>paxta</strong></p>` does not contain the word `paxta` to a
 * `LIKE`. The caller is handed both and stores both.
 */

import { Bold, Heading2, Italic, List, ListOrdered } from "lucide-react"
import { EditorContent, useEditor, type Editor } from "@tiptap/react"
import { StarterKit } from "@tiptap/starter-kit"
import { useEffect } from "react"

import { cn } from "@/lib/cn"

/**
 * Everything the phone app can draw, and nothing else.
 *
 * Each `false` is a node or mark the apps have no renderer for. Adding one
 * back means adding it to two renderers first.
 */
const ALLOWED = StarterKit.configure({
  // Levels, plural, is a list of one: a product description with an h1 and an
  // h3 in it is a document, and this is a paragraph or two under a name that
  // is already the page's heading.
  heading: { levels: [2] },
  bold: {},
  italic: {},
  bulletList: {},
  orderedList: {},
  listItem: {},
  blockquote: false,
  code: false,
  codeBlock: false,
  horizontalRule: false,
  strike: false,
  underline: false,
  link: false,
})

/**
 * Strip what the schema would have dropped anyway — belt and braces for the
 * HTML that arrives *from the server*, which may predate this editor.
 *
 * The editor itself sanitises by parsing into its schema; this exists for the
 * moment before that, when an old description is about to be handed over. A
 * string that has been through `<template>` and back holds no script, no
 * event handler and no element the list below does not name.
 */
export function tidyHtml(html: string): string {
  const keep = new Set(["P", "BR", "STRONG", "B", "EM", "I", "UL", "OL", "LI", "H2"])
  const holder = document.createElement("template")
  holder.innerHTML = html
  const walk = (node: Element) => {
    for (const child of [...node.children]) {
      walk(child)
      if (!keep.has(child.tagName)) child.replaceWith(...child.childNodes)
      // Every attribute goes, including `style` and `on*`: nothing in the
      // allowed set carries one that the apps read.
      else for (const name of [...child.getAttributeNames()]) child.removeAttribute(name)
    }
  }
  walk(holder.content as unknown as Element)
  return holder.innerHTML
}

/** The words in the HTML, for the search index that cannot read markup. */
export function plainText(html: string): string {
  const holder = document.createElement("template")
  holder.innerHTML = html
  return (holder.content.textContent ?? "").replace(/\s+/g, " ").trim()
}

/** An editor with nothing typed into it still holds `<p></p>`. */
export function isBlank(html: string): boolean {
  return plainText(html) === ""
}

function Tool({
  editor,
  active,
  label,
  onPress,
  children,
}: {
  editor: Editor
  active: boolean
  label: string
  onPress: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      // The editor loses its selection to a focused button otherwise, and a
      // bold that applies to nothing is a bold that reads as broken.
      onMouseDown={(event) => event.preventDefault()}
      onClick={() => {
        onPress()
        editor.commands.focus()
      }}
      className={cn(
        "grid size-control-sm place-items-center rounded-control text-ink-soft transition-colors hover:bg-line-soft hover:text-ink [&_svg]:size-4",
        active && "bg-brand-soft text-brand-deep",
      )}
    >
      {children}
    </button>
  )
}

export function RichText({
  value,
  onChange,
  placeholder,
}: {
  /** HTML as stored. */
  value: string
  /** Both halves, every keystroke — the caller decides when to save. */
  onChange: (html: string, text: string) => void
  placeholder?: string
}) {
  const editor = useEditor({
    extensions: [ALLOWED],
    content: value,
    editorProps: {
      attributes: {
        class:
          "min-h-28 px-3 py-2 text-small text-ink outline-none [&_h2]:text-body [&_h2]:font-semibold [&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_p]:mb-1 [&_li]:mb-0.5",
        "aria-label": "Tovar tavsifi",
      },
    },
    onUpdate: ({ editor }) => {
      const html = editor.getHTML()
      onChange(html, plainText(html))
    },
  })

  // The card arrives after the editor is built, so the stored description has
  // to be put in once it lands — and only when it differs, or every keystroke
  // would rewrite the document under the cursor.
  useEffect(() => {
    if (!editor) return
    if (value !== editor.getHTML()) editor.commands.setContent(tidyHtml(value))
    // Deliberately not depending on `editor.getHTML()`: this reacts to the
    // card changing, never to typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, value])

  if (!editor) return null

  const empty = editor.isEmpty

  return (
    <div className="overflow-hidden rounded-control border border-line bg-surface focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/25">
      <div className="flex items-center gap-0.5 border-b border-line bg-line-soft px-1 py-1">
        <Tool
          editor={editor}
          label="Qalin"
          active={editor.isActive("bold")}
          onPress={() => editor.chain().toggleBold().run()}
        >
          <Bold />
        </Tool>
        <Tool
          editor={editor}
          label="Qiyshiq"
          active={editor.isActive("italic")}
          onPress={() => editor.chain().toggleItalic().run()}
        >
          <Italic />
        </Tool>
        <Tool
          editor={editor}
          label="Sarlavha"
          active={editor.isActive("heading", { level: 2 })}
          onPress={() => editor.chain().toggleHeading({ level: 2 }).run()}
        >
          <Heading2 />
        </Tool>
        <span className="mx-1 h-4 w-px bg-line" />
        <Tool
          editor={editor}
          label="Belgili ro'yxat"
          active={editor.isActive("bulletList")}
          onPress={() => editor.chain().toggleBulletList().run()}
        >
          <List />
        </Tool>
        <Tool
          editor={editor}
          label="Raqamli ro'yxat"
          active={editor.isActive("orderedList")}
          onPress={() => editor.chain().toggleOrderedList().run()}
        >
          <ListOrdered />
        </Tool>
      </div>

      <div className="relative">
        {empty && placeholder ? (
          <p className="pointer-events-none absolute px-3 py-2 text-small text-ink-faint">
            {placeholder}
          </p>
        ) : null}
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}
