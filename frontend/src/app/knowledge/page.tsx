"use client";

import { useState } from "react";
import { BookOpen, HelpCircle, Lightbulb, FileText, ChevronRight, Search } from "lucide-react";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { useListKnowledgeItemsApiV1KnowledgeGet } from "@/api/generated/knowledge/knowledge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { KnowledgeItemRead } from "@/api/generated/model";

export default function KnowledgePage() {
    const [activeTab, setActiveTab] = useState("all");
    const [searchQuery, setSearchQuery] = useState("");

    const query = useListKnowledgeItemsApiV1KnowledgeGet({
        status: "approved",
    });

    const items: KnowledgeItemRead[] = query.data?.status === 200 ? query.data.data.items : [];
    const isLoading = query.isLoading;

    const filteredItems = items.filter((item) => {
        const matchesTab = activeTab === "all" || item.item_type === activeTab;
        const matchesSearch =
            item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (item.summary?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false);
        return matchesTab && matchesSearch;
    });

    return (
        <DashboardPageLayout
            title="知识资产库"
            description="自动从任务执行、沟通记录及日常决策中提炼的结构化知识库。"
            signedOut={{
                message: "请登录以访问知识库",
                forceRedirectUrl: "/knowledge",
            }}
        >
            <div className="space-y-6">
                <div className="flex flex-col md:flex-row gap-4 md:items-center justify-between">
                    <Tabs defaultValue="all" className="w-full md:w-auto" onValueChange={setActiveTab}>
                        <TabsList className="bg-white border border-slate-200 shadow-sm">
                            <TabsTrigger value="all">全部</TabsTrigger>
                            <TabsTrigger value="faq">FAQ</TabsTrigger>
                            <TabsTrigger value="decision">决策方案</TabsTrigger>
                            <TabsTrigger value="summary">任务总结</TabsTrigger>
                            <TabsTrigger value="context">背景上下文</TabsTrigger>
                        </TabsList>
                    </Tabs>

                    <div className="relative w-full md:w-72">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                        <Input
                            placeholder="搜索知识..."
                            className="pl-9 bg-white border-slate-200"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                {isLoading ? (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {[1, 2, 3, 4, 5, 6].map(i => (
                            <div key={i} className="h-48 rounded-xl bg-slate-100 animate-pulse border border-slate-200" />
                        ))}
                    </div>
                ) : filteredItems.length > 0 ? (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {filteredItems.map((item) => (
                            <KnowledgeCard key={item.id} item={item} />
                        ))}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-24 bg-white rounded-2xl border border-slate-200 shadow-sm">
                        <div className="bg-slate-50 p-4 rounded-full mb-4">
                            <BookOpen className="h-8 w-8 text-slate-300" />
                        </div>
                        <h3 className="text-lg font-semibold text-slate-900">
                            {searchQuery ? "未找到相关内容" : "暂无知识条目"}
                        </h3>
                        <p className="text-slate-500 text-sm mt-1 max-w-xs text-center">
                            {searchQuery ? `关键词 "${searchQuery}" 没有匹配到任何结果。` : "系统尚未沉淀任何已通过审批的知识资产。"}
                        </p>
                    </div>
                )}
            </div>
        </DashboardPageLayout>
    );
}

function KnowledgeCard({ item }: { item: KnowledgeItemRead }) {
    const IconMap: Record<string, React.ComponentType<{ className?: string }>> = {
        faq: HelpCircle,
        decision: Lightbulb,
        summary: FileText,
        context: BookOpen,
    };
    const Icon = IconMap[item.item_type] || BookOpen;

    const typeLabels: Record<string, string> = {
        faq: "常见问题",
        decision: "决策方案",
        summary: "任务总结",
        context: "背景上下文",
    };

    return (
        <Card className="flex flex-col overflow-hidden group hover:border-blue-400 hover:shadow-lg transition-all duration-300 border-slate-200 shadow-sm bg-white">
            <CardHeader className="pb-3 border-b border-slate-50 bg-slate-50/30 group-hover:bg-blue-50/30 transition-colors">
                <div className="flex items-start justify-between">
                    <Badge
                        variant="default"
                        className="mb-2 bg-blue-50 text-blue-700 border-blue-100 hover:bg-blue-100 transition-colors lowercase tracking-normal"
                    >
                        {typeLabels[item.item_type] || item.item_type}
                    </Badge>
                    <div className="p-2 bg-white rounded-lg border border-slate-100 shadow-sm group-hover:border-blue-100 group-hover:bg-blue-50 transition-all">
                        <Icon className="h-4 w-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
                    </div>
                </div>
                <CardTitle className="text-base font-semibold text-slate-900 group-hover:text-blue-700 transition-colors leading-snug">
                    {item.title}
                </CardTitle>
                <CardDescription className="text-[10px] text-slate-400 mt-1">
                    更新于 {new Date(item.updated_at).toLocaleDateString('zh-CN')}
                </CardDescription>
            </CardHeader>
            <CardContent className="pt-4 flex-1">
                <p className="text-sm text-slate-600 line-clamp-4 leading-relaxed italic border-l-2 border-slate-100 pl-3 mb-4 group-hover:border-blue-200 transition-colors">
                    {item.summary || item.content}
                </p>
                <div className="mt-auto flex items-center justify-between">
                    <span className="text-[11px] text-slate-400">
                        #{item.id.slice(0, 8)}
                    </span>
                    <button className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 transition-colors">
                        详细阅读
                        <ChevronRight className="h-3 w-3" />
                    </button>
                </div>
            </CardContent>
        </Card>
    );
}
