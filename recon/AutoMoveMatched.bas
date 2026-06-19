Attribute VB_Name = "AutoMoveMatched"
' ===================================================================
' GST Reconciliation - Manual Match Mover
' Moves rows ticked TRUE in "Move to Matched?" from any unmatched tab
' into "Matched (Exact)", mapping each field into the correct column,
' tagging match_source = "Manual", then DELETING the row from source.
' One-time setup per file: Alt+F11 > File > Import File > this .bas.
' Run: press Alt+F8 > MoveCheckedRows > Run  (or add a button).
' ===================================================================
Option Explicit

Private Function ColIndex(ws As Worksheet, header As String) As Long
    Dim c As Long
    ColIndex = 0
    For c = 1 To 80
        If Trim(CStr(ws.Cells(1, c).Value)) = header Then ColIndex = c: Exit Function
        If Len(Trim(CStr(ws.Cells(1, c).Value))) = 0 And c > 40 Then Exit For
    Next c
End Function

Private Sub PutVal(mt As Worksheet, nr As Long, header As String, v As Variant)
    Dim c As Long: c = ColIndex(mt, header)
    If c > 0 Then mt.Cells(nr, c).Value = v
End Sub

Public Sub MoveCheckedRows()
    Dim ws As Worksheet, mt As Worksheet
    Dim chkC As Long, lastRow As Long, nr As Long, r As Long
    Dim moved As Long: moved = 0
    Dim toMove As Long: toMove = 0
    Dim isBooks As Boolean
    Set mt = ThisWorkbook.Sheets("Matched (Exact)")

    ' --- count first, then confirm (first line of defence) ---
    For Each ws In ThisWorkbook.Worksheets
        If ws.Name Like "Unmatched*" Or ws.Name Like "Cross-period*" Then
            chkC = ColIndex(ws, "Move to Matched?")
            If chkC > 0 Then
                lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
                For r = 2 To lastRow
                    If UCase(Trim(CStr(ws.Cells(r, chkC).Value))) = "TRUE" Then toMove = toMove + 1
                Next r
            End If
        End If
    Next ws
    If toMove = 0 Then
        MsgBox "No rows are ticked TRUE. Nothing to move.", vbInformation, "GST Recon"
        Exit Sub
    End If
    If MsgBox("Move " & toMove & " row(s) to 'Matched (Exact)'?" & vbCrLf & vbCrLf & _
              "This cannot be undone with Ctrl+Z, but you can reverse it later " & _
              "with MoveBackToUnmatched.", vbQuestion + vbYesNo, "Confirm move") <> vbYes Then
        Exit Sub
    End If

    Application.ScreenUpdating = False
    Application.EnableEvents = False

    For Each ws In ThisWorkbook.Worksheets
        If ws.Name Like "Unmatched*" Or ws.Name Like "Cross-period*" Then
            chkC = ColIndex(ws, "Move to Matched?")
            If chkC > 0 Then
                ' Books tab has 'book_id'; IMS tabs have 'ims_id'
                isBooks = (ColIndex(ws, "book_id") > 0)
                lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
                For r = lastRow To 2 Step -1
                    If UCase(Trim(CStr(ws.Cells(r, chkC).Value))) = "TRUE" Then
                        nr = mt.Cells(mt.Rows.Count, 1).End(xlUp).Row + 1
                        ' common
                        PutVal mt, nr, "match_source", "Manual"
                        PutVal mt, nr, "source_file", IIf(isBooks, "Books", "IMS")
                        PutVal mt, nr, "tier", "MANUAL"
                        PutVal mt, nr, "confidence", 100
                        PutVal mt, nr, "gstin_match", "Y"
                        ' unified fields the master tab links to (taxable/per-head/date)
                        PutVal mt, nr, "taxable_value", ws.Cells(r, ColIndex(ws, "taxable")).Value
                        PutVal mt, nr, "cgst", ws.Cells(r, ColIndex(ws, "cgst")).Value
                        PutVal mt, nr, "sgst", ws.Cells(r, ColIndex(ws, "sgst")).Value
                        PutVal mt, nr, "igst", ws.Cells(r, ColIndex(ws, "igst")).Value
                        If isBooks Then
                            PutVal mt, nr, "date", ws.Cells(r, ColIndex(ws, "date")).Value
                            PutVal mt, nr, "book_gstin", ws.Cells(r, ColIndex(ws, "gstin")).Value
                            PutVal mt, nr, "book_supplier", ws.Cells(r, ColIndex(ws, "supplier")).Value
                            PutVal mt, nr, "book_ref_no", ws.Cells(r, ColIndex(ws, "ref_no")).Value
                            PutVal mt, nr, "book_total_tax", ws.Cells(r, ColIndex(ws, "total_tax")).Value
                            PutVal mt, nr, "book_entry_count", 1
                        Else
                            PutVal mt, nr, "date", ws.Cells(r, ColIndex(ws, "inv_date")).Value
                            PutVal mt, nr, "book_gstin", ws.Cells(r, ColIndex(ws, "gstin")).Value
                            PutVal mt, nr, "ims_gstin", ws.Cells(r, ColIndex(ws, "gstin")).Value
                            PutVal mt, nr, "book_supplier", ws.Cells(r, ColIndex(ws, "name")).Value
                            PutVal mt, nr, "ims_supplier", ws.Cells(r, ColIndex(ws, "name")).Value
                            PutVal mt, nr, "book_ref_no", ws.Cells(r, ColIndex(ws, "inv_no")).Value
                            PutVal mt, nr, "ims_inv_no", ws.Cells(r, ColIndex(ws, "inv_no")).Value
                            PutVal mt, nr, "ims_status", ws.Cells(r, ColIndex(ws, "status")).Value
                            PutVal mt, nr, "ims_total_tax", ws.Cells(r, ColIndex(ws, "total_tax")).Value
                            PutVal mt, nr, "book_total_tax", ws.Cells(r, ColIndex(ws, "total_tax")).Value
                            PutVal mt, nr, "ims_invoice_count", 1
                        End If
                        ' store a machine-parseable origin tag so reversal is automatic
                        PutVal mt, nr, "note", "Manual confirmed | origin=[" & ws.Name & "]"
                        ws.Rows(r).Delete
                        moved = moved + 1
                    End If
                Next r
            End If
        End If
    Next ws

    Application.EnableEvents = True
    Application.ScreenUpdating = True
    RebuildMaster
    MsgBox moved & " row(s) moved to 'Matched (Exact)' as Manual matches.", vbInformation, "GST Recon"
End Sub

' ===================================================================
' Reverse a mistaken manual move. Select any cell(s) on the rows you
' want to send back in 'Matched (Exact)', then run this. Only rows with
' match_source = "Manual" are reversible; each is auto-routed back to its
' origin tab (read from the note's origin=[...] tag). Engine matches are
' protected and will be skipped.
' ===================================================================
Public Sub MoveBackToUnmatched()
    Dim mt As Worksheet: Set mt = ThisWorkbook.Sheets("Matched (Exact)")
    If ActiveSheet.Name <> mt.Name Then
        MsgBox "Go to the 'Matched (Exact)' tab, select the row(s) to reverse, then run this.", _
               vbExclamation, "GST Recon": Exit Sub
    End If

    Dim srcC As Long: srcC = ColIndex(mt, "match_source")
    Dim noteC As Long: noteC = ColIndex(mt, "note")
    Dim sel As Range, rowsHit As Object
    Set rowsHit = CreateObject("Scripting.Dictionary")
    For Each sel In Selection.Cells
        If sel.Row > 1 Then rowsHit(sel.Row) = True
    Next sel
    If rowsHit.Count = 0 Then
        MsgBox "Select at least one data row to reverse.", vbExclamation, "GST Recon": Exit Sub
    End If

    ' collect target rows, validate they are Manual
    Dim rowsArr() As Long, n As Long: n = 0
    ReDim rowsArr(1 To rowsHit.Count)
    Dim k As Variant, skipped As Long: skipped = 0
    For Each k In rowsHit.Keys
        If Trim(CStr(mt.Cells(CLng(k), srcC).Value)) = "Manual" Then
            n = n + 1: rowsArr(n) = CLng(k)
        Else
            skipped = skipped + 1
        End If
    Next k
    If n = 0 Then
        MsgBox "None of the selected rows are Manual matches. Engine matches are protected.", _
               vbExclamation, "GST Recon": Exit Sub
    End If
    If MsgBox("Send " & n & " row(s) back to their origin unmatched tab?" & _
              IIf(skipped > 0, vbCrLf & skipped & " engine match(es) will be skipped.", ""), _
              vbQuestion + vbYesNo, "Confirm reverse") <> vbYes Then Exit Sub

    ' sort descending so deletes don't shift pending rows
    Dim i As Long, j As Long, t As Long
    For i = 1 To n - 1
        For j = i + 1 To n
            If rowsArr(j) > rowsArr(i) Then t = rowsArr(i): rowsArr(i) = rowsArr(j): rowsArr(j) = t
        Next j
    Next i

    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Dim done As Long: done = 0
    For i = 1 To n
        Dim rr As Long: rr = rowsArr(i)
        Dim note As String: note = CStr(mt.Cells(rr, noteC).Value)
        Dim origin As String: origin = ""
        Dim p1 As Long, p2 As Long
        p1 = InStr(note, "origin=[")
        If p1 > 0 Then
            p2 = InStr(p1, note, "]")
            If p2 > p1 Then origin = Mid(note, p1 + 8, p2 - (p1 + 8))
        End If
        If origin = "" Then
            MsgBox "Row " & rr & " has no origin tag; skipping. Move it back manually.", vbExclamation
        ElseIf Not WorksheetExists(origin) Then
            MsgBox "Origin tab '" & origin & "' not found for row " & rr & "; skipping.", vbExclamation
        Else
            Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(origin)
            Dim chkC As Long: chkC = ColIndex(ws, "Move to Matched?")
            Dim isBooks As Boolean: isBooks = (ColIndex(ws, "book_id") > 0)
            ' find next free row using the GSTIN column (always populated), not col 1,
            ' because the id column (book_id/ims_id) is not written on reverse
            Dim gcol As Long: gcol = ColIndex(ws, "gstin")
            Dim nr As Long: nr = ws.Cells(ws.Rows.Count, gcol).End(xlUp).Row + 1
            If nr < 2 Then nr = 2
            ' put a marker in the id column (col 1) so row-counts that scan col 1 see it
            If isBooks Then
                ws.Cells(nr, ColIndex(ws, "book_id")).Value = "MANUAL"
            Else
                ws.Cells(nr, ColIndex(ws, "ims_id")).Value = "MANUAL"
            End If
            If isBooks Then
                ws.Cells(nr, ColIndex(ws, "gstin")).Value = mt.Cells(rr, ColIndex(mt, "book_gstin")).Value
                ws.Cells(nr, ColIndex(ws, "supplier")).Value = mt.Cells(rr, ColIndex(mt, "book_supplier")).Value
                ws.Cells(nr, ColIndex(ws, "ref_no")).Value = mt.Cells(rr, ColIndex(mt, "book_ref_no")).Value
                ws.Cells(nr, ColIndex(ws, "total_tax")).Value = mt.Cells(rr, ColIndex(mt, "book_total_tax")).Value
                ws.Cells(nr, ColIndex(ws, "date")).Value = mt.Cells(rr, ColIndex(mt, "date")).Value
            Else
                ws.Cells(nr, ColIndex(ws, "gstin")).Value = mt.Cells(rr, ColIndex(mt, "ims_gstin")).Value
                ws.Cells(nr, ColIndex(ws, "name")).Value = mt.Cells(rr, ColIndex(mt, "ims_supplier")).Value
                ws.Cells(nr, ColIndex(ws, "inv_no")).Value = mt.Cells(rr, ColIndex(mt, "ims_inv_no")).Value
                ws.Cells(nr, ColIndex(ws, "status")).Value = mt.Cells(rr, ColIndex(mt, "ims_status")).Value
                ws.Cells(nr, ColIndex(ws, "total_tax")).Value = mt.Cells(rr, ColIndex(mt, "ims_total_tax")).Value
                ws.Cells(nr, ColIndex(ws, "inv_date")).Value = mt.Cells(rr, ColIndex(mt, "date")).Value
            End If
            ' carry taxable + per-head back so the master link resolves
            ws.Cells(nr, ColIndex(ws, "taxable")).Value = mt.Cells(rr, ColIndex(mt, "taxable_value")).Value
            ws.Cells(nr, ColIndex(ws, "cgst")).Value = mt.Cells(rr, ColIndex(mt, "cgst")).Value
            ws.Cells(nr, ColIndex(ws, "sgst")).Value = mt.Cells(rr, ColIndex(mt, "sgst")).Value
            ws.Cells(nr, ColIndex(ws, "igst")).Value = mt.Cells(rr, ColIndex(mt, "igst")).Value
            ' tag this restored row as a manual entry; source_file matches the tab type
            If ColIndex(ws, "match_source") > 0 Then ws.Cells(nr, ColIndex(ws, "match_source")).Value = "Manual"
            If ColIndex(ws, "source_file") > 0 Then ws.Cells(nr, ColIndex(ws, "source_file")).Value = IIf(isBooks, "Books", "IMS")
            If chkC > 0 Then ws.Cells(nr, chkC).Value = "FALSE"
            mt.Rows(rr).Delete
            done = done + 1
        End If
    Next i

    Application.EnableEvents = True
    Application.ScreenUpdating = True
    RebuildMaster
    MsgBox done & " row(s) sent back to their origin tab(s).", vbInformation, "GST Recon"
End Sub

Private Function WorksheetExists(nm As String) As Boolean
    Dim w As Worksheet
    On Error Resume Next
    Set w = ThisWorkbook.Sheets(nm)
    WorksheetExists = Not w Is Nothing
    On Error GoTo 0
End Function

' ===================================================================
' Rebuild both consolidated tabs (live-linked) after any move/reverse.
' 'All Transactions' includes all 6 source tabs; 'GSTR3B Working'
' includes only the matched-side tabs (GSTR-3B filing set).
' ===================================================================
Private Function HdrCol(ws As Worksheet, header As String) As Long
    Dim c As Long
    HdrCol = 0
    For c = 1 To 90
        If Trim(CStr(ws.Cells(1, c).Value)) = header Then HdrCol = c: Exit Function
    Next c
End Function

Public Sub RebuildMaster()
    RebuildOneMaster "All Transactions", True
    RebuildOneMaster "GSTR3B Working", False
End Sub

' includeAll = True  -> all six source tabs (full ledger)
' includeAll = False -> only the three matched-side tabs (GSTR3B working set)
Private Sub RebuildOneMaster(masterName As String, includeAll As Boolean)
    If Not WorksheetExists(masterName) Then Exit Sub
    Dim mw As Worksheet: Set mw = ThisWorkbook.Sheets(masterName)

    Application.ScreenUpdating = False
    Application.EnableEvents = False

    ' clear existing data rows (keep title row1 + header row3); 11 cols now
    Dim lastr As Long: lastr = mw.Cells(mw.Rows.Count, 9).End(xlUp).Row
    If lastr >= 4 Then mw.Range("A4:K" & lastr).Clear

    ' source tabs included
    Dim n As Long, names() As String
    If includeAll Then
        n = 6
        ReDim names(1 To 6)
        names(1) = "Matched (Exact)": names(2) = "Review (Fuzzy+Agg)"
        names(3) = "Carry-Forward Matches": names(4) = "Unmatched - Books only"
        names(5) = "Unmatched IMS (same period)": names(6) = "Cross-period IMS (timing)"
    Else
        n = 3
        ReDim names(1 To 3)
        names(1) = "Matched (Exact)": names(2) = "Review (Fuzzy+Agg)"
        names(3) = "Carry-Forward Matches"
    End If

    Dim outR As Long: outR = 4
    Dim k As Long
    For k = 1 To n
        If WorksheetExists(names(k)) Then
            Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(names(k))
            Dim supC$, gstC$, invC$, taxC$, cgC$, sgC$, igC$, dtC$
            Select Case names(k)
                Case "Matched (Exact)", "Review (Fuzzy+Agg)"
                    supC = "book_supplier": gstC = "book_gstin": invC = "book_ref_no"
                    taxC = "taxable_value": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "date"
                Case "Carry-Forward Matches"
                    supC = "ims_supplier": gstC = "gstin": invC = "ims_inv_no"
                    taxC = "taxable_value": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "date"
                Case "Unmatched - Books only"
                    supC = "supplier": gstC = "gstin": invC = "ref_no"
                    taxC = "taxable": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "date"
                Case Else  ' IMS unmatched / cross-period
                    supC = "name": gstC = "gstin": invC = "inv_no"
                    taxC = "taxable": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "inv_date"
            End Select

            Dim cS&, cG&, cI&, cT&, cC&, cSg&, cIg&, cD&, cMS&, cSF&
            cS = HdrCol(ws, supC): cG = HdrCol(ws, gstC): cI = HdrCol(ws, invC)
            cT = HdrCol(ws, taxC): cC = HdrCol(ws, cgC): cSg = HdrCol(ws, sgC)
            cIg = HdrCol(ws, igC): cD = HdrCol(ws, dtC)
            cMS = HdrCol(ws, "match_source"): cSF = HdrCol(ws, "source_file")

            ' count by GSTIN col (always populated); manually-restored rows safe
            Dim lr As Long: lr = ws.Cells(ws.Rows.Count, cG).End(xlUp).Row
            Dim r As Long
            For r = 2 To lr
                If Len(Trim(CStr(ws.Cells(r, cG).Value))) > 0 Then
                    Dim q$: q = "'" & Replace(names(k), "'", "''") & "'!"
                    If cS > 0 Then mw.Cells(outR, 1).Formula = "=" & q & ws.Cells(r, cS).Address(False, False)
                    If cG > 0 Then mw.Cells(outR, 2).Formula = "=" & q & ws.Cells(r, cG).Address(False, False)
                    If cI > 0 Then mw.Cells(outR, 3).Formula = "=" & q & ws.Cells(r, cI).Address(False, False)
                    If cT > 0 Then mw.Cells(outR, 4).Formula = "=" & q & ws.Cells(r, cT).Address(False, False)
                    If cC > 0 Then mw.Cells(outR, 5).Formula = "=" & q & ws.Cells(r, cC).Address(False, False)
                    If cSg > 0 Then mw.Cells(outR, 6).Formula = "=" & q & ws.Cells(r, cSg).Address(False, False)
                    If cIg > 0 Then mw.Cells(outR, 7).Formula = "=" & q & ws.Cells(r, cIg).Address(False, False)
                    If cD > 0 Then mw.Cells(outR, 8).Formula = "=" & q & ws.Cells(r, cD).Address(False, False)
                    mw.Cells(outR, 9).Value = names(k)
                    ' Origin (col 10) -> live link to match_source if available
                    If cMS > 0 Then
                        mw.Cells(outR, 10).Formula = "=" & q & ws.Cells(r, cMS).Address(False, False)
                    Else
                        mw.Cells(outR, 10).Value = "Engine"
                    End If
                    ' Source File (col 11) -> live link to source_file if available
                    If cSF > 0 Then
                        mw.Cells(outR, 11).Formula = "=" & q & ws.Cells(r, cSF).Address(False, False)
                    Else
                        ' fall back to a constant inferred from the tab type
                        Select Case names(k)
                            Case "Matched (Exact)", "Review (Fuzzy+Agg)", "Unmatched - Books only"
                                mw.Cells(outR, 11).Value = "Books"
                            Case Else
                                mw.Cells(outR, 11).Value = "IMS"
                        End Select
                    End If
                    outR = outR + 1
                End If
            Next r
        End If
    Next k

    Application.EnableEvents = True
    Application.ScreenUpdating = True
End Sub
