%% Start of file `awesome-cv.cls'.
% Awesome CV Class File
%
% This class has been downloaded from:
% https://github.com/posquit0/Awesome-CV
%
% Author:
% Claud D. Park <posquit0.bj@gmail.com>
% http://www.posquit0.com
%
% Notes:
% 1) This class file defines the structure and layout of the template file (cv.tex, resume.tex).
% 2) It has been written in such a way that under most circumstances you
% should not need to edit it.
%
% Class license:
% LPPL v1.3c (http://www.latex-project.org/lppl)
%


%-------------------------------------------------------------------------------
%                Identification
%-------------------------------------------------------------------------------
\ProvidesClass{awesome-cv-resume}[2017/02/05 v1.6.1 Awesome Curriculum Vitae Class]
\NeedsTeXFormat{LaTeX2e}


%-------------------------------------------------------------------------------
%                Class options
%-------------------------------------------------------------------------------
\DeclareOption{draft}{\setlength\overfullrule{5pt}}
\DeclareOption{final}{\setlength\overfullrule{0pt}}
\DeclareOption*{%
  \PassOptionsToClass{\CurrentOption}{article}
}
\ProcessOptions\relax
\LoadClass{article}


%-------------------------------------------------------------------------------
%                3rd party packages
%-------------------------------------------------------------------------------
\RequirePackage{array}
\RequirePackage{tabularx}
\RequirePackage{enumitem}
\RequirePackage{ragged2e}
\RequirePackage{geometry}
\RequirePackage{fancyhdr}
\RequirePackage{xcolor}
\RequirePackage{ifxetex}
\RequirePackage{xifthen}
\RequirePackage{xstring}
\RequirePackage{etoolbox}
\RequirePackage{setspace}
\RequirePackage[quiet]{fontspec}
\defaultfontfeatures{Ligatures=TeX}
% \scshape auto-invokes the body font's OpenType smcp feature. XeTeX's
% ToUnicode mapping for those substituted glyphs is unreliable (e.g. i/s
% land on dotless-i/long-s), breaking copy-paste and automated text
% extraction. \XeTeXgenerateactualtext wraps substituted runs in a PDF
% ActualText span carrying the correct original text.
\XeTeXgenerateactualtext=1
\RequirePackage{unicode-math}
\RequirePackage{fontawesome5}
\providecommand{\faEnvelope}{}\providecommand{\faHome}{}\providecommand{\faMapMarker}{}\providecommand{\faGithub}{}\providecommand{\faLinkedinSquare}{}\providecommand{\faOrcid}{}\providecommand{\faHouseChimney}{}\providecommand{\faSquareGithub}{}\providecommand{\faLinkedin}{}\providecommand{\faMobile}{}\providecommand{\faSquareWhatsapp}{}\providecommand{\faCakeCandles}{}\providecommand{\faGitlab}{}\providecommand{\faBitbucket}{}\providecommand{\faStackOverflow}{}\providecommand{\faGraduationCap}{}\providecommand{\faHackerrank}{}\providecommand{\faKaggle}{}\providecommand{\faMastodon}{}\providecommand{\faMedium}{}\providecommand{\faReddit}{}\providecommand{\faResearchgate}{}\providecommand{\faSkype}{}\providecommand{\faSquareXing}{}\providecommand{\faTelegram}{}\providecommand{\faTwitter}{}\providecommand{\faXTwitter}{}
\RequirePackage{accsupp}
\defaultfontfeatures{
  Renderer=HarfBuzz,
}

%-------------------------------------------------------------------------------
%                Configuration for directory locations
%-------------------------------------------------------------------------------
\newcommand*{\fontdir}[1][fonts/]{\def\@fontdir{#1}}
\fontdir  % initialise with default 'fonts/'

%-------------------------------------------------------------------------------
%                Font loading (hardcoded path to avoid expansion timing issue)
%-------------------------------------------------------------------------------
\newfontfamily\headerfont[
  Path=fonts/,
  UprightFont=SourceSans3-Regular.ttf,
  ItalicFont=SourceSans3-Italic.ttf,
  BoldFont=SourceSans3-Bold.ttf,
  BoldItalicFont=SourceSans3-BoldItalic.ttf,
]{SourceSans3}

\newfontfamily\headerfontlight[
  Path=fonts/,
  UprightFont=SourceSans3-Light.ttf,
  ItalicFont=SourceSans3-LightItalic.ttf,
  BoldFont=SourceSans3-SemiBold.ttf,
  BoldItalicFont=SourceSans3-SemiBoldItalic.ttf,
]{SourceSans3}

\setmainfont[
  Path=fonts/,
  UprightFont=SourceSans3-Regular.ttf,
  ItalicFont=SourceSans3-Italic.ttf,
  BoldFont=SourceSans3-Bold.ttf,
  BoldItalicFont=SourceSans3-BoldItalic.ttf,
]{SourceSans3}

% \setsansfont[
%   Path=fonts/,
%   UprightFont=SourceSans3-Regular.ttf,
%   ItalicFont=SourceSans3-Italic.ttf,
%   BoldFont=SourceSans3-Bold.ttf,
%   BoldItalicFont=SourceSans3-BoldItalic.ttf,
% ]{SourceSans3}
\setsansfont[
  Path=fonts/,
  UprightFont=SourceSans3-Regular.ttf,
  ItalicFont=SourceSans3-Italic.ttf,
  BoldFont=SourceSans3-Bold.ttf,
  BoldItalicFont=SourceSans3-BoldItalic.ttf,
  FontFace={l}{n}{SourceSans3-Light.ttf},
  FontFace={l}{it}{SourceSans3-LightItalic.ttf},
  FontFace={l}{sl}{SourceSans3-LightItalic.ttf},
]{SourceSans3}

\newfontfamily\roboto[
  Path=fonts/,
  UprightFont=Roboto-Regular.ttf,
  ItalicFont=Roboto-Italic.ttf,
  BoldFont=Roboto-Bold.ttf,
  BoldItalicFont=Roboto-BoldItalic.ttf,
]{Roboto}

% Needed for the photo ID
% Note: [skins] omitted — triggers a spurious pgfkeys error in TeX Live 2025.
% Safe to omit since \photo is not used in this CV.
\RequirePackage{tcolorbox}
% Needed to deal a paragraphs
\RequirePackage{parskip}
% Needed to deal hyperlink
\RequirePackage[hidelinks,unicode,pdfpagelabels=false]{hyperref}
\hypersetup{%
  pdftitle={},
  pdfauthor={},
  pdfsubject={},
  pdfkeywords={}
}
\RequirePackage{bookmark}


%-------------------------------------------------------------------------------
%                Configuration for layout
%-------------------------------------------------------------------------------
\geometry{left=2.0cm, top=1.5cm, right=2.0cm, bottom=2.0cm, footskip=.5cm}

\fancyhfoffset{0em}
\renewcommand{\headrulewidth}{0pt}
\fancyhf{}
\pagestyle{fancy}


%-------------------------------------------------------------------------------
%                Configuration for colors
%-------------------------------------------------------------------------------
\definecolor{white}{HTML}{FFFFFF}
\definecolor{black}{HTML}{000000}
\definecolor{darkgray}{HTML}{333333}
\definecolor{gray}{HTML}{5D5D5D}
\definecolor{lightgray}{HTML}{999999}
\definecolor{green}{HTML}{C2E15F}
\definecolor{orange}{HTML}{FDA333}
\definecolor{purple}{HTML}{D3A4F9}
\definecolor{red}{HTML}{FB4485}
\definecolor{blue}{HTML}{6CE0F1}
\definecolor{darktext}{HTML}{414141}
\colorlet{text}{darkgray}
\colorlet{graytext}{gray}
\colorlet{lighttext}{lightgray}
\colorlet{sectiondivider}{gray}
\definecolor{awesome-emerald}{HTML}{00A388}
\definecolor{awesome-skyblue}{HTML}{0395DE}
\definecolor{awesome-red}{HTML}{DC3522}
\definecolor{awesome-pink}{HTML}{EF4089}
\definecolor{awesome-orange}{HTML}{FF6138}
\definecolor{awesome-nephritis}{HTML}{27AE60}
\definecolor{awesome-concrete}{HTML}{95A5A6}
\definecolor{awesome-darknight}{HTML}{131A28}
\colorlet{awesome}{awesome-red}

\newbool{acvSectionColorHighlight}
\setbool{acvSectionColorHighlight}{true}


%-------------------------------------------------------------------------------
%                Configuration for fonts
%-------------------------------------------------------------------------------
% NOTE: \headerfont and \headerfontlight are defined above via \newfontfamily.
% Only the body/footer font shorthands are defined here.
\newcommand*{\footerfont}{\sffamily}
\newcommand*{\bodyfont}{\sffamily}
\newcommand*{\bodyfontlight}{\sffamily\fontseries{l}\selectfont}


%-------------------------------------------------------------------------------
%                Configuration for styles
%-------------------------------------------------------------------------------
\newcommand*{\headerfirstnamestyle}[1]{{\fontsize{32pt}{1em}\headerfontlight\color{graytext} #1}}
\newcommand*{\headerlastnamestyle}[1]{{\fontsize{32pt}{1em}\headerfont\bfseries\color{text} #1}}
\newcommand*{\headerpositionstyle}[1]{{\fontsize{7.6pt}{1em}\bodyfont\scshape\color{awesome} #1}}
\newcommand*{\headeraddressstyle}[1]{{\fontsize{8pt}{1em}\headerfont\itshape\color{lighttext} #1}}
\newcommand*{\headersocialstyle}[1]{{\fontsize{6.8pt}{1em}\headerfont\color{text} #1}}
\newcommand*{\headerquotestyle}[1]{{\fontsize{9pt}{1em}\bodyfont\itshape\color{darktext} #1}}
\newcommand*{\footerstyle}[1]{{\fontsize{8pt}{1em}\footerfont\scshape\color{lighttext} #1}}
\newcommand*{\sectionstyleface}[1]{{\fontsize{16pt}{1em}\bodyfont\bfseries #1}}
\newcommand*{\sectionstyle}[1]{%
  \def\@acvSectionTmp{#1}
  \ifthenelse{\boolean{acvSectionColorHighlight}}{%
    \StrSplit{\@acvSectionTmp}{3}{\acvSectionStringAwesome}{\acvSectionStringPlain}%
      \color{awesome}\sectionstyleface{\acvSectionStringAwesome%
      \color{text}{\acvSectionStringPlain}}}%
      {\color{text}\sectionstyleface{\@acvSectionTmp}}}
\newcommand*{\subsectionstyle}[1]{{\fontsize{12pt}{1em}\bodyfont\scshape\textcolor{text}{#1}}}
\newcommand*{\paragraphstyle}{\fontsize{9pt}{1em}\bodyfontlight\upshape\color{text}}

\newcommand*{\entrytitlestyle}[1]{{\fontsize{10pt}{1em}\bodyfont\bfseries\color{darktext} #1}}
\newcommand*{\entrypositionstyle}[1]{{\fontsize{8pt}{1em}\bodyfont\scshape\color{graytext} #1}}
\newcommand*{\entrydatestyle}[1]{{\fontsize{8pt}{1em}\bodyfontlight\slshape\color{graytext} #1}}
\newcommand*{\entrylocationstyle}[1]{{\fontsize{9pt}{1em}\bodyfontlight\slshape\color{awesome} #1}}
\newcommand*{\descriptionstyle}[1]{{\fontsize{9pt}{1em}\bodyfontlight\upshape\color{text} #1}}

\newcommand*{\subentrytitlestyle}[1]{{\fontsize{8pt}{1em}\bodyfont\mdseries\color{graytext} #1}}
\newcommand*{\subentrypositionstyle}[1]{{\fontsize{7pt}{1em}\bodyfont\scshape\color{graytext} #1}}
\newcommand*{\subentrydatestyle}[1]{{\fontsize{7pt}{1em}\bodyfontlight\slshape\color{graytext} #1}}
\newcommand*{\subentrylocationstyle}[1]{{\fontsize{7pt}{1em}\bodyfontlight\slshape\color{awesome} #1}}
\newcommand*{\subdescriptionstyle}[1]{{\fontsize{8pt}{1em}\bodyfontlight\upshape\color{text} #1}}

\newcommand*{\honortitlestyle}[1]{{\fontsize{9pt}{1em}\bodyfont\color{graytext} #1}}
\newcommand*{\honorpositionstyle}[1]{{\fontsize{9pt}{1em}\bodyfont\bfseries\color{darktext} #1}}
\newcommand*{\honordatestyle}[1]{{\fontsize{9pt}{1em}\bodyfont\color{graytext} #1}}
\newcommand*{\honorlocationstyle}[1]{{\fontsize{9pt}{1em}\bodyfontlight\slshape\color{awesome} #1}}

\newcommand*{\skilltypestyle}[1]{{\fontsize{10pt}{1em}\bodyfont\bfseries\color{darktext} #1}}
\newcommand*{\skillsetstyle}[1]{{\fontsize{9pt}{1em}\bodyfontlight\color{text} #1}}

\newcommand*{\lettersectionstyleface}[1]{{\fontsize{14pt}{1em}\bodyfont\bfseries #1}}
\newcommand*{\lettersectionstyle}[1]{%
  \def\@acvLetterSectionTmp{#1}
  \ifthenelse{\boolean{acvSectionColorHighlight}}{%
    \StrSplit{\@acvLetterSectionTmp}{3}{\acvLetterSectionStringAwesome}{\acvLetterSectionStringPlain}%
      \color{awesome}\sectionstyleface{\acvLetterSectionStringAwesome%
      \color{text}{\acvLetterSectionStringPlain}}}%
      {\color{text}\lettersectionstyleface{\@acvLetterSectionTmp}}}
\newcommand*{\recipientaddressstyle}[1]{{\fontsize{9pt}{1em}\bodyfont\scshape\color{graytext} #1}}
\newcommand*{\recipienttitlestyle}[1]{{\fontsize{11pt}{1em}\bodyfont\bfseries\color{darktext} #1}}
\newcommand*{\lettertitlestyle}[1]{{\fontsize{10pt}{1em}\bodyfontlight\bfseries\color{darktext} \underline{#1}}}
\newcommand*{\letterdatestyle}[1]{{\fontsize{9pt}{1em}\bodyfontlight\slshape\color{graytext} #1}}
\newcommand*{\lettertextstyle}{\fontsize{10pt}{1.4em}\bodyfontlight\upshape\color{graytext}}
\newcommand*{\letternamestyle}[1]{{\fontsize{10pt}{1em}\bodyfont\bfseries\color{darktext} #1}}
\newcommand*{\letterenclosurestyle}[1]{{\fontsize{10pt}{1em}\bodyfontlight\slshape\color{lighttext} #1}}


%-------------------------------------------------------------------------------
%                Commands for personal information
%-------------------------------------------------------------------------------
\newcommand{\photo}[2][circle,edge,left]{%
  \def\@photo{#2}
  \@for\tmp:=#1\do{%
    \ifthenelse{\equal{\tmp}{circle} \or \equal{\tmp}{rectangle}}%
      {\let\@photoshape\tmp}{}%
    \ifthenelse{\equal{\tmp}{edge} \or \equal{\tmp}{noedge}}%
      {\let\@photoedge\tmp}{}%
    \ifthenelse{\equal{\tmp}{left} \or \equal{\tmp}{right}}%
      {\let\@photoalign\tmp}{}%
  }%
}
\def\@photoshape{circle}
\def\@photoedge{edge}
\def\@photoalign{left}

\newcommand*{\name}[2]{\def\@firstname{#1}\def\@lastname{#2}}
\newcommand*{\firstname}[1]{\def\@firstname{#1}}
\newcommand*{\lastname}[1]{\def\@lastname{#1}}
\newcommand*{\familyname}[1]{\def\@lastname{#1}}
\def\@familyname{\@lastname}

\newcommand*{\address}[1]{\def\@address{#1}}
\newcommand*{\position}[1]{\def\@position{#1}}

\newcommand*{\mobile}[1]
{
  \def\@mobile{#1}
  \def\@teluri{tel:\@mobile}
  \StrDel{\@teluri}{ }[\@teluri]%
  \StrDel{\@teluri}{-}[\@teluri]%
  \StrDel{\@teluri}{(}[\@teluri]%
  \StrDel{\@teluri}{)}[\@teluri]%
}

\newcommand*{\whatsapp}[1]
{
  \def\@whatsapp{#1}
  \def\@wameuri{https://wa.me/\@whatsapp}
  \StrDel{\@wameuri}{ }[\@wameuri]%
  \StrDel{\@wameuri}{+}[\@wameuri]%
  \StrDel{\@wameuri}{-}[\@wameuri]%
  \StrDel{\@wameuri}{(}[\@wameuri]%
  \StrDel{\@wameuri}{)}[\@wameuri]%
}

\newcommand*{\email}[1]{\def\@email{#1}}
\newcommand*{\dateofbirth}[1]{\def\@dateofbirth{#1}}
\newcommand*{\homepage}[1]{\def\@homepage{#1}}
\newcommand*{\github}[1]{\def\@github{#1}}
\newcommand*{\gitlab}[1]{\def\@gitlab{#1}}
\newcommand*{\bitbucket}[1]{\def\@bitbucket{#1}}
\newcommand*{\stackoverflow}[2]{\def\@stackoverflowid{#1}\def\@stackoverflowname{#2}}
\newcommand*{\linkedin}[1]{\def\@linkedin{#1}}
\newcommand*{\orcid}[1]{\def\@orcid{#1}}
\newcommand*{\twitter}[1]{\def\@twitter{#1}}
\newcommand*{\x}[1]{\def\@x{#1}}
\newcommand*{\mastodon}[2]{\def\@mastodoninstance{#1}\def\@mastodonname{#2}}
\newcommand*{\researchgate}[1]{\def\@researchgate{#1}}
\newcommand*{\skype}[1]{\def\@skype{#1}}
\newcommand*{\reddit}[1]{\def\@reddit{#1}}
\newcommand*{\xing}[1]{\def\@xing{#1}}
\newcommand*{\medium}[1]{\def\@medium{#1}}
\newcommand*{\kaggle}[1]{\def\@kaggle{#1}}
\newcommand*{\hackerrank}[1]{\def\@hackerrank{#1}}
\newcommand*{\telegram}[1]{\def\@telegram{#1}}

\newcommand*{\googlescholar}[2]{%
  \def\@googlescholarid{#1}%
  \ifthenelse{\equal{#2}{}}{%
    \def\@googlescholarname{\@firstname~\@lastname}%
  }{%
    \def\@googlescholarname{#2}%
  }%
}

\newcommand*{\extrainfo}[1]{\def\@extrainfo{#1}}
\renewcommand*{\quote}[1]{\def\@quote{#1}}

\newcommand*{\recipient}[2]{\def\@recipientname{#1}\def\@recipientaddress{#2}}
\newcommand*{\recipientname}[1]{\def\@recipientname{#1}}
\newcommand*{\recipientaddress}[1]{\def\@recipientaddress{#1}}
\newcommand*{\lettertitle}[1]{\def\@lettertitle{#1}}
\newcommand*{\letterdate}[1]{\def\@letterdate{#1}}
\newcommand*{\letteropening}[1]{\def\@letteropening{#1}}
\newcommand*{\letterclosing}[1]{\def\@letterclosing{#1}}
\newcommand*{\letterenclname}[1][Enclosure]{\def\@letterenclname{#1}}
\newcommand*{\letterenclosure}[2][]{%
  \ifthenelse{\equal{#1}{}}{}{\def\@letterenclname{#1}}
  \def\@letterenclosure{#2}
}


%-------------------------------------------------------------------------------
%                Commands for extra
%-------------------------------------------------------------------------------
\newcommand{\acvHeaderNameDelim}{\space}
\newcommand{\acvHeaderAfterNameSkip}{.4mm}
\newcommand{\acvHeaderAfterPositionSkip}{.4mm}
\newcommand{\acvHeaderAfterAddressSkip}{-.5mm}
\newcommand{\acvHeaderIconSep}{\space}
\newcommand{\acvHeaderSocialSep}{\BeginAccSupp{ActualText={}}\quad\textbar\quad\EndAccSupp{}}
\newcommand{\acvHeaderAfterSocialSkip}{6mm}
\newcommand{\acvHeaderAfterQuoteSkip}{5mm}

\newcommand{\acvSectionTopSkip}{3mm}
\newcommand{\acvSectionContentTopSkip}{2.5mm}


%-------------------------------------------------------------------------------
%                Commands for utilities
%-------------------------------------------------------------------------------
\renewcommand{\tabularxcolumn}{p}
\newcolumntype{L}[1]{>{\raggedright\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}
\newcolumntype{C}[1]{>{\centering\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}
\newcolumntype{R}[1]{>{\raggedleft\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}

\def\vhrulefill#1{\leavevmode\leaders\hrule\@height#1\hfill \kern\z@}

\newcommand*{\ifempty}[3]{\ifthenelse{\isempty{#1}}{#2}{#3}}

\newcommand{\faAlt}[3]{%
  \BeginAccSupp{ActualText={#1}}%
    \mbox{#2\acvHeaderIconSep#3}%
  \EndAccSupp{}%
}

%-------------------------------------------------------------------------------
%                Commands for elements of CV structure
%-------------------------------------------------------------------------------
\newcommand*{\makecvheader}[1][C]{%
  \newcommand*{\drawphoto}{%
    \ifthenelse{\isundefined{\@photo}}{}{%
      \newlength{\photodim}
      \ifthenelse{\equal{\@photoshape}{circle}}%
        {\setlength{\photodim}{1.3cm}}%
        {\setlength{\photodim}{1.8cm}}%
      \ifthenelse{\equal{\@photoedge}{edge}}%
        {\def\@photoborder{darkgray}}%
        {\def\@photoborder{none}}%
      \begin{tikzpicture}%
        \node[\@photoshape, draw=\@photoborder, line width=0.3mm, inner sep=\photodim, fill overzoom image=\@photo] () {};
      \end{tikzpicture}
    }%
  }
  \newlength{\headertextwidth}
  \newlength{\headerphotowidth}
  \ifthenelse{\isundefined{\@photo}}{
    \setlength{\headertextwidth}{\textwidth}
    \setlength{\headerphotowidth}{0cm}
  }{%
    \setlength{\headertextwidth}{0.76\textwidth}
    \setlength{\headerphotowidth}{0.24\textwidth}
  }%
  \begin{minipage}[c]{\headerphotowidth}%
    \ifthenelse{\equal{\@photoalign}{left}}{\raggedright\drawphoto}{}
  \end{minipage}
  \begin{minipage}[c]{\headertextwidth}
    \ifthenelse{\equal{#1}{L}}{\raggedright}{\ifthenelse{\equal{#1}{R}}{\raggedleft}{\centering}}
    \headerfirstnamestyle{\@firstname}\headerlastnamestyle{{}\acvHeaderNameDelim\@lastname}%
    \\[\acvHeaderAfterNameSkip]%
    \ifthenelse{\isundefined{\@position}}{}{\headerpositionstyle{\@position\\[\acvHeaderAfterPositionSkip]}}%
    \ifthenelse{\isundefined{\@address}}{}{\headeraddressstyle{\@address\\[\acvHeaderAfterAddressSkip]}}%
    \headersocialstyle{%
      \newbool{isstart}%
      \setbool{isstart}{true}%
      \ifthenelse{\isundefined{\@mobile}}%
        {}%
        {%
          \href{\@teluri}{\faAlt{tel:\@mobile}{\faMobile}{\@mobile}}%
          \setbool{isstart}{false}%
        }%
      \ifthenelse{\isundefined{\@whatsapp}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{\@wameuri}{\faAlt{WhatsApp: \@whatsapp}{\faSquareWhatsapp}{\@whatsapp}}%
        }%
      \ifthenelse{\isundefined{\@email}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{mailto:\@email}{\faAlt{mailto:\@email}{\faEnvelope}{\@email}}%
        }%
      \ifthenelse{\isundefined{\@dateofbirth}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \faAlt{DoB: \@dateofbirth}{\faCakeCandles}{\@dateofbirth}%
        }%
      \ifthenelse{\isundefined{\@homepage}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          % \href{\@homepage}{\faAlt{homepage: \@homepage}{\faHouseChimney}{\@homepage}}%
          \href{\@homepage}{\faAlt{homepage: \@homepage}{\faHome}{\@homepage}}%
        }%
      \ifthenelse{\isundefined{\@github}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          % \href{https://github.com/\@github}{\faAlt{GitHub: @\@github}{\faSquareGithub}{\@github}}%
          \href{https://github.com/\@github}{\faAlt{GitHub: @\@github}{\faGithubSquare}{\@github}}%
        }%
      \ifthenelse{\isundefined{\@gitlab}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://gitlab.com/\@gitlab}{\faAlt{GitLab: @\@gitlab}{\faGitlab}{\@gitlab}}%
        }%
      \ifthenelse{\isundefined{\@bitbucket}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://bitbucket.com/\@bitbucket}{\faAlt{BitBucket: @\@bitbucket}{\faBitbucket}{\@bitbucket}}%
        }%
      \ifthenelse{\isundefined{\@stackoverflowid}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://stackoverflow.com/users/\@stackoverflowid}{\faAlt{StackOverflow: @\@stackoverflowname}{\faStackOverflow}{\@stackoverflowname}}%
        }%
      \ifthenelse{\isundefined{\@linkedin}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://www.linkedin.com/in/\@linkedin}{\faAlt{LinkedIn: /in/\@linkedin}{\faLinkedin}{\@linkedin}}%
        }%
      \ifthenelse{\isundefined{\@orcid}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://orcid.org/\@orcid}{\faAlt{OrcID: \@orcid}{\faOrcid}{\@orcid}}%
        }%
      \ifthenelse{\isundefined{\@twitter}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://twitter.com/\@twitter}{\faAlt{Twitter: @\@twitter}{\faTwitter}{\@twitter}}%
        }%
      \ifthenelse{\isundefined{\@x}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://x.com/\@x}{\faAlt{X: @\@x}{\faXTwitter}{\@x}}%
        }%
      \ifthenelse{\isundefined{\@mastodonname}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://\@mastodoninstance/@\@mastodonname}{\faAlt{Mastodon: \@mastodonname{}@\@mastodoninstance}{\faMastodon}{\@mastodonname}}%
        }%
      \ifthenelse{\isundefined{\@skype}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \faAlt{Skype: \@skype}{\faSkype}{\@skype}%
        }%
      \ifthenelse{\isundefined{\@reddit}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://www.reddit.com/user/\@reddit}{\faAlt{Reddit: /u/\@reddit}{\faReddit}{\@reddit}}%
        }%
      \ifthenelse{\isundefined{\@researchgate}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://www.researchgate.net/profile/\@researchgate}{\faAlt{ResearchGate: \@researchgate}{\faResearchgate}{\@researchgate}}%
        }%
      \ifthenelse{\isundefined{\@xing}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://www.xing.com/profile/\@xing}{\faAlt{Xing: \@xing}{\faSquareXing}{\@xing}}
        }%
      \ifthenelse{\isundefined{\@medium}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://medium.com/@\@medium}{\faAlt{Medium: @\@medium}{\faMedium}{\@medium}}%
        }%
      \ifthenelse{\isundefined{\@kaggle}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://kaggle.com/\@kaggle}{\faAlt{Kaggle: \@kaggle}{\faKaggle}{\@kaggle}}%
        }%
      \ifthenelse{\isundefined{\@hackerrank}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://www.hackerrank.com/\@hackerrank}{\faAlt{HackerRank: \@hackerrank}{\faHackerrank}{\@hackerrank}}%
        }%
      \ifthenelse{\isundefined{\@telegram}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://t.me/\@telegram}{\faAlt{Telegram: \@telegram}{\faTelegram}{\@telegram}}%
        }%
      \ifthenelse{\isundefined{\@googlescholarid}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://scholar.google.com/citations?user=\@googlescholarid}{\faAlt{Google Scholar: \@googlescholarid}{\faGraduationCap}{\@googlescholarname}}%
        }%
      \ifthenelse{\isundefined{\@extrainfo}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \@extrainfo%
        }%
    } \\[\acvHeaderAfterSocialSkip]%
    \ifthenelse{\isundefined{\@quote}}%
      {}%
      {\headerquotestyle{\@quote\\}\vspace{\acvHeaderAfterQuoteSkip}}%
  \end{minipage}%
  \begin{minipage}[c]{\headerphotowidth}%
    \ifthenelse{\equal{\@photoalign}{right}}{\raggedleft\drawphoto}{}
  \end{minipage}
}

\newcommand*{\makecvfooter}[3]{%
  \fancyfoot{}
  \fancyfoot[L]{\footerstyle{#1}}
  \fancyfoot[C]{\footerstyle{#2}}
  \fancyfoot[R]{\footerstyle{#3}}
}

\newcommand{\cvsection}[1]{%
  \vspace{\acvSectionTopSkip}
  \sectionstyle{#1}
  \phantomsection
  \color{sectiondivider}\vhrulefill{0.9pt}
}

\newcommand{\cvsubsection}[1]{%
  \vspace{\acvSectionContentTopSkip}
  \vspace{-3mm}
  \subsectionstyle{#1}
  \phantomsection
}

\newenvironment{cvparagraph}{%
  \vspace{\acvSectionContentTopSkip}
  \vspace{-1mm}
  \paragraphstyle
}{%
  \par
  \vspace{2mm}
}

\newenvironment{cventries}{%
  \vspace{\acvSectionContentTopSkip}
  \begin{center}
}{%
  \end{center}
}

\newcommand*{\cventry}[5]{%
  \vspace{-2.0mm}
  \setlength\tabcolsep{0pt}
  \setlength{\extrarowheight}{0pt}
  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} L{\textwidth - 4.5cm} R{4.5cm}}
    \ifempty{#2#3}
      {\entrypositionstyle{#1} & \entrydatestyle{#4} \\}
      {\entrytitlestyle{#2} & \entrylocationstyle{#3} \\[-2pt]
      \entrypositionstyle{#1} & \entrydatestyle{#4} \\}
    \ifstrempty{#5}
      {}
      {\multicolumn{2}{L{\textwidth}}{\descriptionstyle{#5}} \\}
  \end{tabular*}%
}

\newenvironment{cvsubentries}{%
  \begin{center}
}{%
  \end{center}
}

\newcommand*{\cvsubentry}[4]{%
  \setlength\tabcolsep{0pt}
  \setlength{\extrarowheight}{0pt}
  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} L{\textwidth - 4.5cm} R{4.5cm}}
    \setlength\leftskip{0.2cm}
    \subentrytitlestyle{#2} & \ifthenelse{\equal{#1}{}}
      {\subentrydatestyle{#3}}{}
    \ifthenelse{\equal{#1}{}}
      {}
      {\subentrypositionstyle{#1} & \subentrydatestyle{#3} \\}
    \ifthenelse{\equal{#4}{}}
      {}
      {\multicolumn{2}{L{17.0cm}}{\subdescriptionstyle{#4}} \\}
  \end{tabular*}
}

\newenvironment{cvhonors}{%
  \vspace{\acvSectionContentTopSkip}
  \vspace{-2mm}
  \begin{center}
    \setlength\tabcolsep{0pt}
    \setlength{\extrarowheight}{0pt}
    \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} C{1.5cm} L{\textwidth - 4.0cm} R{2.5cm}}
}{%
    \end{tabular*}
  \end{center}
}

\newcommand*{\cvhonor}[4]{%
  \honordatestyle{#4} & \honorpositionstyle{#1}\ifempty{#2}{}{,} \honortitlestyle{#2} & \honorlocationstyle{#3} \\
}

\newenvironment{cvskills}{%
  \vspace{\acvSectionContentTopSkip}
  \vspace{-2.0mm}
    \setlength\tabcolsep{0pt}
    \setlength{\extrarowheight}{0pt}
    \tabularx{\textwidth}{l@{\hspace{2em}}>{\raggedright\let\newline\\\arraybackslash\hspace{0pt}}X}
}{%
\endtabularx\par
}

\newcommand*{\cvskill}[2]{%
  \skilltypestyle{#1} & \leavevmode\skillsetstyle{#2} \\
}

\newenvironment{cvitems}{%
  \vspace{-4.0mm}
  \begin{itemize}[leftmargin=2ex, nosep, itemsep=1.5pt]
    \setlength{\parskip}{0pt}
    \renewcommand{\labelitemi}{\bullet}
}{%
  \end{itemize}
  \vspace{1.0mm}
}


%-------------------------------------------------------------------------------
%                Commands for elements of Cover Letter
%-------------------------------------------------------------------------------
\newenvironment{cvletter}{%
  \lettertextstyle
}{%
}

\newcommand{\lettersection}[1]{%
  \par\addvspace{2.5ex}
  \phantomsection{}
  \lettersectionstyle{#1}
  \color{sectiondivider}\vhrulefill{0.9pt}
  \par\nobreak\addvspace{0.4ex}
  \lettertextstyle
}

\newcommand*{\makelettertitle}{%
  \vspace{8.4mm}
  \setlength\tabcolsep{0pt}
  \setlength{\extrarowheight}{0pt}
  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} L{\textwidth - 4.5cm} R{4.5cm}}
    \recipienttitlestyle{\@recipientname} & \letterdatestyle{\@letterdate}
  \end{tabular*}
  \begin{singlespace}
    \recipientaddressstyle{\@recipientaddress} \\\\
  \end{singlespace}
  \ifthenelse{\isundefined{\@lettertitle}}
    {}
    {\lettertitlestyle{\@lettertitle} \\}
  \lettertextstyle{\@letteropening}
}

\newcommand*{\makeletterclosing}{%
  \vspace{3.4mm}
  \lettertextstyle{\@letterclosing} \\\\
  \letternamestyle{\@firstname\ \@lastname}
  \ifthenelse{\isundefined{\@letterenclosure}}
    {\\}
    {%
      \\\\\\
      \letterenclosurestyle{\@letterenclname: \@letterenclosure} \\
    }
}